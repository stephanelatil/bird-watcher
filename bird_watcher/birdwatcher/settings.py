from pathlib import Path
from decouple import Csv, Config, RepositoryEnv

__all__ = ['env']

env_path_dir = Path.cwd()
#not top directory and env does not exist
while env_path_dir != env_path_dir.parent and not env_path_dir.joinpath('.env').exists():
    env_path_dir = env_path_dir.parent #look up one dir
if env_path_dir == env_path_dir.parent:
    print("Unable to find .env file!")
    exit(1)

env = Config(RepositoryEnv(str(env_path_dir.joinpath('.env').absolute())))
