import * as functions from 'firebase-functions'
import * as admin from 'firebase-admin'
import { format, addDays, parseISO } from 'date-fns'

if (!admin.apps.length) admin.initializeApp()

const db = admin.firestore()

/**
 * Scheduled function: runs daily to carry standing orders forward by one day.
 * Reads all standing orders for today under the active voyage and writes copies
 * with tomorrow's service_date. Idempotent — skips if a copy already exists.
 *
 * Schedule: "0 3 * * *" (3 AM UTC — adjust to run before cutoff_hour)
 */
export const carryStandingOrders = functions.pubsub
  .schedule('0 3 * * *')
  .timeZone('UTC')
  .onRun(async () => {
    const configSnap = await db.collection('appConfig').doc('settings').get()
    if (!configSnap.exists) {
      console.warn('appConfig/settings not found — skipping standing order carry')
      return null
    }

    const config = configSnap.data()!
    const voyageId: string = config.current_voyage_id
    if (!voyageId) {
      console.warn('No active voyage — skipping')
      return null
    }

    const today = format(new Date(), 'yyyy-MM-dd')
    const tomorrow = format(addDays(new Date(), 1), 'yyyy-MM-dd')

    // Fetch today's standing orders
    const snap = await db
      .collection('voyages').doc(voyageId)
      .collection('preorders')
      .where('standing_order', '==', true)
      .where('service_date', '==', today)
      .get()

    if (snap.empty) {
      console.log(`No standing orders for ${today}`)
      return null
    }

    // Check which ones already have a copy for tomorrow (idempotency)
    const existingSnap = await db
      .collection('voyages').doc(voyageId)
      .collection('preorders')
      .where('standing_order', '==', true)
      .where('service_date', '==', tomorrow)
      .get()

    const existingKeys = new Set(
      existingSnap.docs.map((d) => {
        const data = d.data()
        return `${data.cabin_number}|${data.guest_name}|${data.dish}|${data.service_time_slot}|${data.venue_id}`
      })
    )

    const BATCH_SIZE = 499
    let batch = db.batch()
    let count = 0

    for (const docSnap of snap.docs) {
      const src = docSnap.data()
      const key = `${src.cabin_number}|${src.guest_name}|${src.dish}|${src.service_time_slot}|${src.venue_id}`

      if (existingKeys.has(key)) continue

      const newRef = db
        .collection('voyages').doc(voyageId)
        .collection('preorders')
        .doc()

      batch.set(newRef, {
        ...src,
        service_date: tomorrow,
        chef_flag: false,
        chef_remark: '',
        created_at: admin.firestore.FieldValue.serverTimestamp(),
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      })

      count++

      if (count % BATCH_SIZE === 0) {
        await batch.commit()
        batch = db.batch()
      }
    }

    if (count % BATCH_SIZE !== 0) await batch.commit()

    console.log(`Carried ${count} standing orders from ${today} → ${tomorrow}`)
    return null
  })
