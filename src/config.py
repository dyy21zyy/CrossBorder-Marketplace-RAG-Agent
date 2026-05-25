from dotenv import load_dotenv
import yaml

def load_config(path: str = 'configs/default.yaml'):
    load_dotenv()
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
