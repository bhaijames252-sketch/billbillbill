import json
import time
import pika
from .main import ResourcePuller 


def push_message(message):
    print("DATA SENT")
    print(message)
    credentials = pika.PlainCredentials("appuser", "secretpassword")
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="10.0.3.1", port=5672, credentials=credentials)
    )
    channel = connection.channel()

    channel.queue_declare(queue="cloud-bill", durable=True)

    channel.basic_publish(
        exchange="",
        routing_key="cloud-bill",
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2)  
    )

    connection.close()



if __name__ == "__main__":
    while 1<2:
        puller = ResourcePuller()
        push_message(puller.pull_data())
        time.sleep(10)
