from gcn_kafka import Consumer

# Connect as a consumer
consumer = Consumer(client_id='5doe3c3rq1l0gkholg2thshft5',
                    client_secret='1mu69psb6t3m7a6ioccj5vsqje02qk1epfsqbb7d8d9ar23tgegs')

# List all available topics
print("利用可能なトピックを取得しています...")
topics = consumer.list_topics().topics

# Print each topic name
for topic in topics:
    print(topic)

print("\n取得完了。")
