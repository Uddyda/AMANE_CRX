import { Kafka } from 'gcn-kafka'

// Create a client.
// Warning: don't share the client secret with others.
const kafka = new Kafka({
  client_id: '5doe3c3rq1l0gkholg2thshft5',
  client_secret: '1mu69psb6t3m7a6ioccj5vsqje02qk1epfsqbb7d8d9ar23tgegs',
})

// Subscribe to topics and receive alerts
const consumer = kafka.consumer()
try {
  await consumer.subscribe({
    topics: [
        'gcn.notices.icecube.lvk_nu_track_search',
        'gcn.notices.superk.sn_alert',
    ],
  })
} catch (error) {
  if (error.type === 'TOPIC_AUTHORIZATION_FAILED')
  {
    console.warn('Not all subscribed topics are available')
  } else {
    throw error
  }
}

await consumer.run({
  eachMessage: async (payload) => {
    const value = payload.message.value
    console.log(`topic=${payload.topic}, offset=${payload.message.offset}`)
    console.log(value?.toString())
  },
})