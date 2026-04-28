import os
import base64
import io
import re
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

# Region from user hint
REGION = "us-central1"

class BrandConfig:
    DARK_BLUE = "#070E30"
    SUMMER_YELLOW = "#FFD600"
    WINTER_CYAN = "#00C8DC"
    WHITE = "#FFFFFF"
    
    FONT_BOLD = "fonts/atyp-font/AtypDisplay-Bold.ttf"
    FONT_REGULAR = "fonts/atyp-font/AtypText-Regular.ttf"
    FONT_EXTRABOLD = "fonts/atyp-font/AtypDisplay-Bold.ttf" # Using Bold as fallback since ExtraBold is not available
    
    ASSETS_DIR = "assets"
    
    @classmethod
    def load_from_design_md(cls, design_guidelines):
        # Extract colors if present
        db_match = re.search(r"Sportega Dark Blue:.*?`(#([0-9A-Fa-f]{6}))`", design_guidelines)
        if db_match: cls.DARK_BLUE = db_match.group(1)
        
        sy_match = re.search(r"Sportega Summer Yellow:.*?`(#([0-9A-Fa-f]{6}))`", design_guidelines)
        if sy_match: cls.SUMMER_YELLOW = sy_match.group(1)
        
        wc_match = re.search(r"Sportega Winter Cyan:.*?`(#([0-9A-Fa-f]{6}))`", design_guidelines)
        if wc_match: cls.WINTER_CYAN = wc_match.group(1)

def get_client():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    return genai.Client(vertexai=True, project=project_id, location=REGION)

def get_smart_crop_coords(image_bytes):
    """Uses Gemini to find the best 600x400 crop coordinates."""
    try:
        client = get_client()
        mime_type = "image/jpeg" 
            
        prompt = """
        Analyze this image and identify the main subject (product or person).
        I need to crop this image to a 3:2 aspect ratio (specifically for a 600x400 banner).
        Suggest the best cropping box as [ymin, xmin, ymax, xmax] in normalized coordinates (0-1000).
        The crop MUST be 3:2. 
        Return ONLY the coordinates in this format: [ymin, xmin, ymax, xmax].
        """
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt
            ]
        )
        text = response.text.strip()
        match = re.search(r"\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]", text)
        if match:
            return [int(x) for x in match.groups()]
    except Exception as e:
        print(f"Warning: Gemini smart crop failed ({e}). Falling back to center crop.")
    
    return [166, 0, 833, 1000]

def get_font(font_name, size):
    """Loads a font from assets or falls back to system fonts."""
    font_path = os.path.join(BrandConfig.ASSETS_DIR, font_name)
    if os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except:
            pass
    
    # Fallback paths
    fallbacks = [
        "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf" if "Bold" in font_name else "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if "Bold" in font_name else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in fallbacks:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()

def create_banner_image(image_bytes, heading, perex, design_guidelines, vendor_name=None):
    """Processes the image and overlays text according to Sportega mailing guidelines."""
    BrandConfig.load_from_design_md(design_guidelines)
    
    coords = get_smart_crop_coords(image_bytes)
    
    img_io = io.BytesIO(image_bytes)
    with Image.open(img_io) as img:
        width, height = img.size
        
        # Crop & Resize
        ymin, xmin, ymax, xmax = coords
        left, top, right, bottom = xmin * width / 1000, ymin * height / 1000, xmax * width / 1000, ymax * height / 1000
        
        target_ratio = 1.5
        current_ratio = (right - left) / (bottom - top) if (bottom - top) > 0 else 1
        
        if current_ratio > target_ratio:
            new_w = (bottom - top) * target_ratio
            cx = (left + right) / 2
            left, right = cx - new_w / 2, cx + new_w / 2
        else:
            new_h = (right - left) / target_ratio
            cy = (top + bottom) / 2
            top, bottom = cy - new_h / 2, cy + new_h / 2
            
        img_cropped = img.crop((left, top, right, bottom))
        img_resized = img_cropped.resize((600, 400), Image.Resampling.LANCZOS).convert("RGBA")
        
        # 1. Draw Dark Overlay (Left side, 60-75% opacity)
        overlay = Image.new("RGBA", (600, 400), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        # Gradient or solid? Guidelines say "Tmavý overlay levo"
        # We'll do a solid block on the left with a slight fade
        overlay_width = 300
        for x in range(overlay_width):
            alpha = int(255 * 0.75 * (1 - (x / overlay_width) ** 2)) # Quadratic fade
            draw_overlay.line([(x, 0), (x, 400)], fill=(0, 0, 0, alpha))
        
        img_final = Image.alpha_composite(img_resized, overlay)
        draw = ImageDraw.Draw(img_final)
        
        # 2. Heading: Atyp Bold/ExtraBold, white, max 3-4 words
        h_font = get_font(BrandConfig.FONT_EXTRABOLD, 40)
        draw.text((30, 40), heading, font=h_font, fill=BrandConfig.WHITE)
        
        # 3. Perex: Atyp Regular, white, max 2 sentences
        p_font = get_font(BrandConfig.FONT_REGULAR, 18)
        # Word wrap for perex
        perex_lines = []
        words = perex.split()
        line = ""
        for word in words:
            test_line = line + word + " "
            if draw.textlength(test_line, font=p_font) < 240:
                line = test_line
            else:
                perex_lines.append(line)
                line = word + " "
        perex_lines.append(line)
        
        y_offset = 120
        for line in perex_lines[:3]: # Limit to 3 lines
            draw.text((30, y_offset), line.strip(), font=p_font, fill=BrandConfig.WHITE)
            y_offset += 25

        # 4. CTA Button: Summer Yellow, Atyp Bold, vlevo dole
        btn_font = get_font(BrandConfig.FONT_BOLD, 18)
        btn_text = "To chci"
        btn_w = draw.textlength(btn_text, font=btn_font) + 40
        btn_h = 45
        btn_x, btn_y = 30, 320
        
        # Rounded rectangle
        draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=15, fill=BrandConfig.SUMMER_YELLOW)
        draw.text((btn_x + 20, btn_y + 10), btn_text, font=btn_font, fill=BrandConfig.DARK_BLUE)
        
        # 5. Logo Partnera: Vpravo nahore
        if vendor_name:
            vendor_logo_path = os.path.join(BrandConfig.ASSETS_DIR, f"{vendor_name.lower()}_logo.png")
            if not os.path.exists(vendor_logo_path):
                # Try generic logo
                vendor_logo_path = os.path.join(BrandConfig.ASSETS_DIR, "vendor_logo.png")
                
            if os.path.exists(vendor_logo_path):
                with Image.open(vendor_logo_path) as logo:
                    logo = logo.convert("RGBA")
                    # Resize logo to fit
                    logo_w, logo_h = logo.size
                    max_logo_w = 120
                    scale = max_logo_w / logo_w
                    logo = logo.resize((int(logo_w * scale), int(logo_h * scale)), Image.Resampling.LANCZOS)
                    img_final.paste(logo, (600 - logo.size[0] - 20, 20), logo)
        
        # Convert back to RGB for PNG save if needed, or keep RGBA
        buf = io.BytesIO()
        img_final.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()
