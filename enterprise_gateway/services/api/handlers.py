import os
pjoin = os.path.join


class MetricGenerator:

    def __init__(self, kernel_session_manager):
        self.ksm = kernel_session_manager

    def generate_metrics(self):
        return self.ksm.get_metrics()
