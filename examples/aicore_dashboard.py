from aicore.observability import ObservabilityDashboard

if __name__ == "__main__":
    od = ObservabilityDashboard(from_local_records_only=True)
    od.run_server()