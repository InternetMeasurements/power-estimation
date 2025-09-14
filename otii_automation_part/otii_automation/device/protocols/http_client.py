import requests
import time


def fetch_payload(server_ip, server_port, filename):
    """ Fetch file from HTTP server without saving it locally """
    url = f"http://{server_ip}:{server_port}/{filename}"

    start_time = time.monotonic_ns()  # Start timestamp
    response = requests.get(url, stream=True)
    stop_time = time.monotonic_ns()  # Stop timestamp

    if response.status_code == 200:
        # Read the file in chunks (but discard it)
        for _ in response.iter_content(1024):
            pass  # Just iterate, don't save

        return start_time, stop_time, 0
    else:
        raise Exception(f"Failed to fetch {filename}: {response.status_code} {response.text}")
