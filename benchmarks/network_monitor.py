import threading
import time

import psutil


class NetworkMonitor:
    def __init__(self, interval=1):
        self.interval = interval
        self.running = False
        self.upload_speeds = []
        self.download_speeds = []

    def _monitor(self):
        prev = psutil.net_io_counters()
        while self.running:
            time.sleep(self.interval)
            current = psutil.net_io_counters()
            upload_speed = (current.bytes_sent - prev.bytes_sent) / self.interval  # B/s
            download_speed = (
                current.bytes_recv - prev.bytes_recv
            ) / self.interval  # B/s
            self.upload_speeds.append(upload_speed)
            self.download_speeds.append(download_speed)
            prev = current

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._monitor)
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()

    def get_average_download_speed(self):
        avg_download = (
            sum(self.download_speeds) / len(self.download_speeds)
            if self.download_speeds
            else 0
        )
        return avg_download

    def get_average_upload_speed(self):
        avg_upload = (
            sum(self.upload_speeds) / len(self.upload_speeds)
            if self.upload_speeds
            else 0
        )
        return avg_upload
