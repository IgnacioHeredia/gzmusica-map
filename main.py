from download import download_events
from generate import generate_html


if __name__ == "__main__":
    download_events()
    generate_html()
    print('Completed')
