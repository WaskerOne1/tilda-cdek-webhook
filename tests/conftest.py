import os

# Set minimal required environment variables for tests so imports won't fail.
os.environ.setdefault('SENDER_LOCATION_CODE', 'SENDER1')
os.environ.setdefault('SENDER_LOCATION_ADDRESS', 'Sender address')
os.environ.setdefault('SENDER_PHONE', '+70000000000')
