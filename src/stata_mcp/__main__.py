from multiprocessing import freeze_support
from .server import main

if __name__ == '__main__':
    freeze_support()
    main()
