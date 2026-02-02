import os
import sys
import shutil
import subprocess

def create_directories():
    dirs = [
        'data',
        'data/logs',
        'data/memory',
        'models',
        'models/wakeword',
        'models/tts',
        'models/whisper'
    ]
    
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"Created directory: {d}")

def create_config_template():
    src = 'host/config/api_keys.template.yaml'
    dst = 'host/config/api_keys.yaml'
    
    if not os.path.exists(dst):
        shutil.copy(src, dst)
        print(f"Created config file: {dst}")
    else:
        print(f"Config file already exists: {dst}")

def install_dependencies():
    print("\nInstalling Python dependencies...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

def setup_venv():
    venv_path = 'venv'
    
    if not os.path.exists(venv_path):
        print(f"\nCreating virtual environment...")
        subprocess.check_call([sys.executable, '-m', 'venv', venv_path])
        print(f"Virtual environment created: {venv_path}")
        
        pip_path = os.path.join(venv_path, 'Scripts', 'pip') if os.name == 'nt' else os.path.join(venv_path, 'bin', 'pip')
        subprocess.check_call([pip_path, 'install', '-r', 'requirements.txt'])
    else:
        print(f"Virtual environment already exists: {venv_path}")

def check_requirements():
    requirements = [
        ('python', '3.9'),
    ]
    
    print("\nChecking requirements...")
    
    if sys.version_info < (3, 9):
        print(f"Error: Python 3.9+ required, found {sys.version}")
        return False
    
    print(f"Python version: {sys.version}")
    return True

def main():
    print("=" * 50)
    print("DaShan Robot Setup")
    print("=" * 50)
    
    if not check_requirements():
        sys.exit(1)
    
    print("\nWhat would you like to do?")
    print("1. Create directories and config files")
    print("2. Install dependencies (system)")
    print("3. Setup virtual environment")
    print("4. Full setup (all of the above)")
    print("5. Exit")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    if choice == '1':
        create_directories()
        create_config_template()
    elif choice == '2':
        install_dependencies()
    elif choice == '3':
        setup_venv()
    elif choice == '4':
        create_directories()
        create_config_template()
        setup_venv()
    elif choice == '5':
        print("Exiting...")
    else:
        print("Invalid choice")
        sys.exit(1)
    
    print("\nSetup complete!")
    print("\nNext steps:")
    print("1. Edit host/config/api_keys.yaml and add your LLM API key")
    print("2. Edit host/config/settings.yaml and configure serial port")
    print("3. Run: python -m host.main")

if __name__ == '__main__':
    main()
