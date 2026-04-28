import os
import base64
import binascii
from . import banner_engine
from google.adk.agents.llm_agent import Agent
from google.adk.tools.tool_context import ToolContext
from google.adk.apps.app import App
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin

def _maybe_base64_to_bytes(data: str) -> bytes | None:
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        return None

async def create_banner(image_path: str, heading: str, perex: str, tool_context: ToolContext, vendor_name: str = None) -> str:
    """Creates an ad banner from an image, heading and perex.
    
    Args:
        image_path: Local path to the input image file, or the name of an uploaded artifact.
        heading: The heading text to be placed on the banner.
        perex: The perex (sub-text) for the banner.
        vendor_name: Optional name of the partner brand (e.g., Babolat, Head).
    """
    image_bytes = None
    
    # 1. Try to load as an ADK artifact (if the user uploaded the image via web UI)
    artifact = await tool_context.load_artifact(image_path)
    if artifact is None and not image_path.startswith('user:'):
        artifact = await tool_context.load_artifact(f'user:{image_path}')
        
    if artifact and artifact.inline_data and artifact.inline_data.data:
        data = artifact.inline_data.data
        if isinstance(data, str):
            decoded = _maybe_base64_to_bytes(data)
            image_bytes = decoded if decoded else data.encode('utf-8')
        else:
            image_bytes = data
            
    if not image_bytes and artifact and artifact.file_data and artifact.file_data.file_uri:
        uri = artifact.file_data.file_uri
        local_path = uri[7:] if uri.startswith('file://') else uri
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                image_bytes = f.read()
            
    # 2. Fallback to reading from local file system if not an artifact
    if not image_bytes:
        if not os.path.exists(image_path):
            # Try to see if it's in the current dir
            if os.path.exists(os.path.join(os.getcwd(), image_path)):
                image_path = os.path.join(os.getcwd(), image_path)
            else:
                available_artifacts = await tool_context.list_artifacts()
                debug_info = f" Available attached artifacts: {available_artifacts}" if available_artifacts else " No attached artifacts found."
                return f"Error: Image file not found at '{image_path}'." + debug_info
        else:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
    
    # Read design guidelines
    design_path = os.path.join(os.path.dirname(__file__), "design.md")
    if os.path.exists(design_path):
        with open(design_path, "r") as f:
            design_guidelines = f.read()
    else:
        design_guidelines = "Follow general professional design standards."
    
    try:
        result_bytes = banner_engine.create_banner_image(image_bytes, heading, perex, design_guidelines, vendor_name=vendor_name)
        
        from google.genai import types
        output_artifact = types.Part.from_bytes(data=result_bytes, mime_type="image/png")
        await tool_context.save_artifact("generated_banner.png", output_artifact)
        
        # We return a markdown image referencing the artifact for preview in adk web
        return f"### Banner Created Successfully!\n\n![Banner Preview](generated_banner.png)\n\nYou can find the generated banner above."
    except Exception as e:
        return f"Error during banner creation: {str(e)}"

# Define the root agent
# Using gemini-2.5-flash as the most stable latest model
root_agent = Agent(
    model='gemini-2.5-flash',
    name='banner_agent',
    description='An agent that creates ad banners for mailing campaigns by resizing images and overlaying text.',
    instruction='''You are a specialized Banner Creation Agent. 
    Your goal is to help users create 600x400 ad banners for mailing campaigns.
    
    When a user provides an image (via local path or attached artifact filename), a heading, and a perex:
    1. Use the 'create_banner' tool to process the request. 
    2. If it's a vendor campaign (e.g., mentions a brand like Babolat or Head), ask for the vendor name if not provided, and pass it to the `vendor_name` parameter.
    3. Pass the filename of the attached artifact or the local path to the `image_path` parameter.
    4. The tool will handle smart cropping (preserving subjects) and text overlay following Sportega guidelines.
    
    If the user doesn't provide the main inputs (image, heading, perex), ask for the missing ones.
    Be professional and helpful.
    ''',
    tools=[create_banner]
)

# Expose as an ADK App to enable plugins like file uploads
app = App(
    name="banner_agent",
    root_agent=root_agent,
    plugins=[SaveFilesAsArtifactsPlugin()]
)

