"""
Streamlit启动脚本
"""
import sys
import os
import subprocess

# Add src directory to path
project_root = os.path.dirname(os.path.abspath(__file__))
# Change to project root to ensure relative paths work correctly
os.chdir(project_root)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

if __name__ == "__main__":
    # Get the path to streamlit_app.py
    streamlit_app_path = os.path.join(
        project_root, 
        'src', 
        'shuai_travel_agent', 
        'streamlit_app.py'
    )
    
    if not os.path.exists(streamlit_app_path):
        print(f"\n❌ Error: Cannot find {streamlit_app_path}\n")
        sys.exit(1)
    
    # Run streamlit with the app file
    try:
        subprocess.run([
            sys.executable, '-m', 'streamlit', 'run', streamlit_app_path
        ], check=True)
    except subprocess.CalledProcessError:
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n❌ Error: Streamlit is not installed.\nPlease run: pip install -r requirements.txt\n")
        sys.exit(1)
