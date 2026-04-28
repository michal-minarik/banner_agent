import os
import io
import base64
from google import genai
from google.genai import types

# Region from user hint
REGION = "us-central1"

def get_client():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    # Using vertexai=True to access Gemini 2.0 Flash with Image generation capabilities
    return genai.Client(vertexai=True, project=project_id, location=REGION)

def create_banner_image(image_bytes, heading, perex, design_guidelines, vendor_name=None):
    """Creates a banner using pure Multimodal LLM generation (Gemini 2.0)."""
    client = get_client()
    
    # Construct the multimodal request for Gemini 2.0 Flash
    # This model can take images as input and produce an image as output (responseModalities=["IMAGE"])
    
    contents = [
        types.Part.from_text(text=f"""You are an expert graphic designer and brand guardian for Sportega.
Your task is to CREATE a 600x400 px banner for a mailing campaign.

DESIGN GUIDELINES:
{design_guidelines}

BANNER CONTENT:
- HEADING: {heading}
- PEREX: {perex}
- VENDOR: {vendor_name if vendor_name else 'None'}

INSTRUCTIONS:
1. OUTPUT: You must respond with a single 600x400 px image.
2. COMPOSITION: Use the provided base image. Regardless of its original aspect ratio, crop or recompose it into a 3:2 frame so the main subject (athlete or product) is prominent.
3. OVERLAY: Apply a dark overlay on the left side (60-75% opacity) to provide a clean area for text, exactly as shown in the example banners.
4. TEXT: 
   - Render the HEADING in a bold, clean, white font on the overlay.
   - Render the PEREX in a regular, clean, white font below the heading.
5. CTA: Include a 'To chci' call-to-action button in Summer Yellow (#FFD600) with Dark Blue (#070E30) text at the bottom left.
6. VENDOR BRANDING: If a vendor is specified, place their logo in the bottom right. 

CONSTRAINTS:
- Make sure that you don't leak font names into the final image
- Make sure that you follow provided design guides

EXAMPLES:
- I am providing example banners for style reference, and the base image to be used for this specific banner.""")
    ]
    
    # 1. Add example images for few-shot visual context
    example_dir = os.path.join(os.path.dirname(__file__), "example-banners")
    print(f"Example directory: {example_dir}")
    if os.path.exists(example_dir):
        # We limit examples to avoid context bloat while providing enough visual grounding
        for filename in sorted(os.listdir(example_dir))[:2]:
            if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                path = os.path.join(example_dir, filename)
                with open(path, "rb") as f:
                    print("attaching image")
                    contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
    
    # 2. Add the base image (the core subject)
    contents.append(types.Part.from_text(text="BASE IMAGE (Use this as the source for the banner):"))
    contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
    
    # 3. Add the vendor logo if applicable
    if vendor_name:
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        # Check subdirectories as well based on previous user info
        vendor_logo_path = os.path.join(assets_dir, f"{vendor_name.lower()}_logo.png")
        if not os.path.exists(vendor_logo_path):
             vendor_logo_path = os.path.join(assets_dir, "logos", f"{vendor_name.lower()}_logo.png")
             
        if os.path.exists(vendor_logo_path):
            with open(vendor_logo_path, "rb") as f:
                contents.append(types.Part.from_text(text=f"VENDOR LOGO for {vendor_name}:"))
                contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))

    # 4. Execute the Multimodal Generation
    # We use gemini-2.5-flash-image which supports multimodal image output
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            )
        )
        
        # Extract the image from the response parts
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                # The GenAI SDK returns images in the 'inline_data' or a specific 'image' field depending on version
                if part.inline_data:
                    return part.inline_data.data
                elif hasattr(part, 'image') and part.image:
                    return part.image.image_bytes
                    
        raise Exception("Gemini returned a success response but no image data was found in the parts.")
        
    except Exception as e:
        # Provide a descriptive error for the agent to report
        raise Exception(f"Multimodal generation failed: {str(e)}. Ensure the model 'gemini-2.0-flash-001' is available and 'IMAGE' modality is supported in your project/region.")

def get_base64_image(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")
