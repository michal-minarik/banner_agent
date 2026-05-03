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

async def create_square_banner(image_path: str, heading: str, perex: str, cta_text: str, tool_context: ToolContext) -> str:
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
    try:
        result_bytes = banner_engine.create_banner_image(image_bytes, heading, perex, cta_text, "1:1")
        
        from google.genai import types
        output_artifact = types.Part.from_bytes(data=result_bytes, mime_type="image/png")
        await tool_context.save_artifact("generated_1_1_banner.png", output_artifact)
        
        # We return a markdown image referencing the artifact for preview in adk web
        return f"Banner generated!"
    except Exception as e:
        return f"Error during banner creation: {str(e)}"

async def create_mailing_banner(image_path: str, heading: str, perex: str, cta_text: str, tool_context: ToolContext) -> str:
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
    try:
        result_bytes = banner_engine.create_banner_image(image_bytes, heading, perex, cta_text, "3:2")
        
        from google.genai import types
        output_artifact = types.Part.from_bytes(data=result_bytes, mime_type="image/png")
        await tool_context.save_artifact("generated_3_2_banner.png", output_artifact)
        
        # We return a markdown image referencing the artifact for preview in adk web
        return f"Banner generated!"
    except Exception as e:
        return f"Error during banner creation: {str(e)}"

# Define the root agent
root_agent = Agent(
    model='gemini-2.5-flash',
    name='banner_agent',
    description='An agent that creates ad banners for mailing campaigns by resizing images and overlaying text.',
    instruction='''You are a specialized Banner Creation Agent. 
    Your goal is to help users create images for mailing campaigns.
    
    ## Inputs
    User will provide image (via local path or attached artifact filename), heading, perex and CTA text in Czech language. 

    ## Main workflow
    Run following workflow and pass the filename of the attached artifact or the local path to the `image_path` parameter.

    1. Use the 'create_mailing_banner' tool to process the request. 
    2. Use the 'create_square_banner' tool to process the request. 
    ''',
    tools=[create_mailing_banner, create_square_banner]
)

# Expose as an ADK App to enable plugins like file uploads
app = App(
    name="banner_agent",
    root_agent=root_agent,
    plugins=[SaveFilesAsArtifactsPlugin()]
)

