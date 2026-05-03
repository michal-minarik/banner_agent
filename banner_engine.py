import os
import base64
from google import genai
from google.genai import types

SYSTEM_PROMPT = """
## Design Guidelines

### Brand Identity

Sportega is a Czech sports e-commerce brand (est. 2002).

- **Mission:** Helping every athlete find gear that truly fits them. Speaking athlete to athlete.
- **Core Values:**
  - **Energy:** Lively, dynamic, full of movement.
  - **Authenticity:** No marketing jargon; human and experience-based.
  - **Relevance:** Useful content for athletes.
  - **Playfulness:** Sport should be fun; humor and wordplay are encouraged.

### Brand Colors

- **Sportega Dark Blue:** `#070E30` 
- **Sportega Summer Yellow:** `#FFD600` - Used for warm sports (outdoor, cycling, tennis, football).
- **Sportega Winter Cyan:** `#00C8DC` - Used for winter sports (hockey, skiing, winter running).

### Logo Usage

- **Primary Colors:** Dark Blue or Summer Yellow.
- **Clear Space:** Minimum clear space equal to the height of the letter 'S' in the logotype.
- **Primary Combination:** Dark Blue + Summer Yellow.
- **Winter Variant:** Dark Blue + Winter Cyan.
- **White:** Neutral background or text on dark surfaces.
- **Never Combine:** Do not mix Summer Yellow and Winter Cyan as equal primary colors on the same surface.
- **Don'ts:** Do not rotate, distort, recolor (outside approved variants), add effects, or use on busy/low-contrast backgrounds.

### Typography

Sportega uses two typefaces to balance professionalism and personality.

#### Primary font: ATYP

- **Usage:** Headlines, body text, UI, emails, banners.
- **Weights:** Regular, Medium, Bold, ExtraBold.

#### Complementary font: NARRABEEN

- **Usage:** Taglines, accents, display headlines, campaign headings. Use sparingly for maximum impact.

#### Hierarchy

- **H1 (Main Headline):** Atyp Bold/ExtraBold, 32–48 pt (Campaigns, hero sections).
- **H2 (Section Heading):** Atyp Bold, 22–28 pt (Pages, chapters).
- **H3 (Subheading):** Atyp Medium/Bold, 16–18 pt (Sub-chapters, categories).
- **Body Text:** Atyp Regular, 10–12 pt.
- **Caption:** Atyp Regular Italic, 8–9 pt.
- **Label:** Atyp Bold, 8–10 pt (UI elements, tags, buttons).

### Visual Elements

- **Doodles:** Hand-drawn, monochromatic (White, Summer Yellow, or Dark Blue). Used as accents, never dominant.
- **Icons:** Clean, functional, aligned with brand colors.
- **Patterns:** Used as background fills or decorative elements (never as primary information).

### Tone of Voice

- **Pillars:**
  - **Friendly & Informal:** Use "tykání" (first-name basis), no anonymous texts.
  - **Clear & Energetic:** Short sentences, rhythm, wordplay, light slang.
  - **Factual but Emotional:** Real benefits, own language, metaphors.
- **Check:** "Would I write about this experience to a friend after training?"

### Do's & Don'ts
- **DO:** Use high-quality images, keep focal points (faces/products) looking into the banner, use dark overlays for readability, follow typographic hierarchy.
- **DON'T:** Use blurry/stock photos, distort logos, use more than 3 typographic layers, mix brand colors inappropriately, or use corporate jargon.
"""


# Region from user hint
REGION = "global"

def get_client():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    return genai.Client(vertexai=True, project=project_id, location=REGION)


def create_banner_image(image_bytes, heading, perex, cta_text, aspect_ratio):
    """Creates a banner using multimodal LLM generation with strict dimension enforcement."""
    client = get_client()
    
    contents = [
        types.Part.from_text(text=f"""
Create a mailing banner with following features:

- Overlay: Add color gradient overlay coming from left. Use the dark blue brand color.
- Font: Make sure you use the correct font from the brand guidelines.
- Headline: Bold font weight. White text color. Put there this exact text {heading}.
- Perex: Regular font weight. White or grey color. Put there this exact text {perex}.
- Vertical Alignment: The Heading and Perex text block must be vertically centered within the dark overlay or positioned in the upper half. Never place the main text at the very bottom.
- CTA Button: Summer Yellow (#FFD600), Bold font weight, bottom left with generous margins. Button should have rounded corners (be pill shaped). Put there this exact text {cta_text}
- Image: High-quality product or athlete.
- Do NOT put a Sportega logo to the image.
""")
    ]
    
    # Attach base image
    contents.append(types.Part.from_text(text="Base image is:"))
    contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

    # Attach samples
    example_dir = os.path.join(os.path.dirname(__file__), "example-banners")
    if os.path.exists(example_dir):
        contents.append(types.Part.from_text(text="Example of previous banners are:"))
        for filename in sorted(os.listdir(example_dir))[:2]:
            if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                path = os.path.join(example_dir, filename)
                with open(path, "rb") as f:
                    contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
    
    # Attach brand assets 
    assets_dir = os.path.join(os.path.dirname(__file__), "assets", "brand_assets.png")
    contents.append(types.Part.from_text(text="Brand assets (like fonts, doodles and icons) are:"))
    with open(path, "rb") as f:
        print("reading assets")
        contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))

    # Execute image generation
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size="1K",
                    output_mime_type="image/png",
                ),
                thinking_config=types.ThinkingConfig(
                    thinking_level="HIGH",
                ) 
            )
        )
        
        image_data = None
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_data = part.inline_data.data
                    break
                elif hasattr(part, 'image') and part.image:
                    image_data = part.image.image_bytes
                    break
                    
        if not image_data:
            raise Exception("Gemini returned no image data.")

        return image_data
            
        
    except Exception as e:
        raise Exception(f"Multimodal generation failed: {str(e)}")

def get_base64_image(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")
