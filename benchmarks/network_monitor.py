import threading
import time

import psutil


class NetworkMonitor:
    def __init__(self, interval=1):
        self.interval = interval
        self.running = False
        self.upload_utilization = []
        self.download_utilization = []

    def _monitor(self):
        prev = psutil.net_io_counters()
        while self.running:
            time.sleep(self.interval)
            current = psutil.net_io_counters()
            upload = (
                (current.bytes_sent - prev.bytes_sent) / self.interval / 1024
            )  # KB/s
            download = (
                (current.bytes_recv - prev.bytes_recv) / self.interval / 1024
            )  # KB/s
            self.upload_utilization.append(upload)
            self.download_utilization.append(download)
            prev = current

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._monitor)
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()

    def get_averages(self):
        avg_upload = (
            sum(self.upload_utilization) / len(self.upload_utilization)
            if self.upload_utilization
            else 0
        )
        avg_download = (
            sum(self.download_utilization) / len(self.download_utilization)
            if self.download_utilization
            else 0
        )
        return avg_upload, avg_download
