"""
FastAPI启动脚本
"""
import sys
import os

# Add src directory to path
project_root = os.path.dirname(os.path.abspath(__file__))
# Change to project root to ensure relative paths work correctly
os.chdir(project_root)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from shuai_travel_agent.app import app, start_server
    from shuai_travel_agent.agent import TravelAgent
except ImportError as e:
    print(f"\n❌ Import Error: {e}")
    print(f"\nMake sure you're running from project root: {project_root}")
    print(f"Python path: {sys.path}\n")
    sys.exit(1)

if __name__ == "__main__":
    # Load Web service configuration
    try:
        # Use relative path from project root
        config_path = os.path.join('config', 'config.json')
        temp_agent = TravelAgent(config_path=config_path)
        web_config = temp_agent.config_manager.get_config('web', {})
        start_server(
            host=web_config.get('host', '0.0.0.0'),
            port=web_config.get('port', 8000),
            reload=web_config.get('debug', True)
        )
    except FileNotFoundError as e:
        print(f"\n❌ Configuration Error:\n{str(e)}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Startup Error: {str(e)}\n")
        sys.exit(1)
