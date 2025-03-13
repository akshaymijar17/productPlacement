import streamlit as st
import time
import traceback
from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task

# -----------------------------------------------------------------------------
# 1. SETUP & CONFIGURATION
# -----------------------------------------------------------------------------

# Remove the hardcoded API_KEY and read from secrets.
# Make sure you have "TWELVELABS_API_KEY" set in your secrets (local .toml or Streamlit Cloud).
st.set_page_config(page_title="Product Placement Assistant", layout="centered")

def create_twelvelabs_client() -> TwelveLabs:
    """
    Create and return a TwelveLabs client instance, pulling the API key from st.secrets.
    """
    api_key = st.secrets["TWELVELABS_API_KEY"]
    return TwelveLabs(api_key=api_key)

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def create_index(client: TwelveLabs, index_name: str):
    """
    Create a new 12Labs index with specified models/addons.
    """
    models = [
        {"name": "marengo2.7", "options": ["visual", "audio"]},
        {"name": "pegasus1.2", "options": ["visual", "audio"]},
    ]
    try:
        created_index = client.index.create(
            name=index_name,
            models=models,
            addons=["thumbnail"]
        )
        return created_index
    except Exception as e:
        raise RuntimeError(f"Failed to create index: {e}")


def upload_video_and_wait(client: TwelveLabs, index_id: str, video_file):
    """
    Upload the video to the specified index and wait for indexing to complete.
    Updates the status message in place every 30 seconds.
    """
    try:
        task = client.task.create(
            index_id=index_id,
            file=video_file,
        )

        # Create a placeholder to update status in place.
        status_placeholder = st.empty()

        def on_task_update(t: Task):
            # Update the same placeholder each time
            status_placeholder.write(f"Indexing Status: {t.status}")

        # Sleep interval = 30s, so it updates the placeholder every 30 seconds
        task.wait_for_done(sleep_interval=30, callback=on_task_update)

        if task.status != "ready":
            raise RuntimeError(f"Indexing failed with status '{task.status}'")

        return task.video_id
    except Exception as e:
        raise RuntimeError(f"Video upload/indexing failed: {e}")


def generate_text_from_video(client: TwelveLabs, video_id: str, prompt: str) -> str:
    """
    Generate text from an indexed video using the provided prompt.
    """
    try:
        result = client.generate.text(video_id=video_id, prompt=prompt, temperature=0.7)
        return result.data
    except Exception as e:
        raise RuntimeError(f"Text generation failed: {e}")


# -----------------------------------------------------------------------------
# 3. STREAMLIT APP
# -----------------------------------------------------------------------------

def main():
    """
    1) Prompt input (text_area) for brand placement query.
    2) Displays file uploader.
    3) Creates an index on button click, then uploads & indexes the video.
    4) Generates text from the video and displays the result.
    """

    st.title("Product Placement Assistant")
    st.write("Upload a video and click 'Analyze' to generate product placement insights.")

    # Let the user specify the prompt
    user_prompt = st.text_area(
        label="Prompt",
        value="Analyze the video and provide segments of the video that are ideal for brand placements.",
        help="Which products do you want to place within the video?"
    )

    # Initialize session-state variables
    if "index_id" not in st.session_state:
        st.session_state.index_id = None
    if "video_id" not in st.session_state:
        st.session_state.video_id = None

    # File uploader
    uploaded_file = st.file_uploader(
        "Upload your video",
        type=["mp4", "mov", "avi"],
        help="Please upload a valid video file.",
    )

    if st.button("Analyze"):
        # Basic validation
        if not uploaded_file:
            st.error("No video file provided. Please upload a valid file.")
            return

        # Initialize 12Labs client
        try:
            client = create_twelvelabs_client()
        except Exception:
            st.error("Could not initialize 12Labs client. Check your API key setup in st.secrets.")
            return

        # 1) Create Index with a dynamic name (using the current timestamp)
        index_name = f"my_product_index_{int(time.time())}"
        try:
            with st.spinner("Creating a new 12Labs index..."):
                created_index = create_index(client, index_name)
            st.success(f"Index created: {created_index.name} (ID: {created_index.id})")
            st.session_state.index_id = created_index.id
        except RuntimeError as e:
            st.error(f"Oops, it's not you—it's us. Please try again.\n\nDetails: {e}")
            return

        # 2) Upload and Index Video
        try:
            with st.spinner("Uploading and indexing your video. Please wait..."):
                video_id = upload_video_and_wait(client, created_index.id, uploaded_file)
            st.session_state.video_id = video_id
            st.success("Video indexing completed successfully!")
        except RuntimeError as e:
            st.error(f"Oops, it's not you—it's us. Please try again.\n\nDetails: {e}")
            return

        # 3) Generate Text with the user-provided prompt
        try:
            with st.spinner("Generating text from your video..."):
                generated_text = generate_text_from_video(client, video_id, user_prompt)
            st.success("Text generation successful!")
            st.write("## Product placement insights")
            st.write(generated_text)
        except RuntimeError as e:
            st.error(f"Oops, it's not you—it's us. Please try again.\n\nDetails: {e}")
            return


# -----------------------------------------------------------------------------
# 4. ENTRY POINT
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()