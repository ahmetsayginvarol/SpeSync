import * as functions from 'firebase-functions'
import * as admin from 'firebase-admin'
import * as Papa from 'papaparse'

if (!admin.apps.length) admin.initializeApp()

const db = admin.firestore()
const storage = admin.storage()

/**
 * Storage-triggered function: fires when a CSV is uploaded to /imports/{voyageId}/*.csv
 * Parses the CSV, validates required columns (cabin_number, first_name, last_name),
 * and batch-writes guests under the voyage.
 */
export const importGuestsOnUpload = functions.storage.object().onFinalize(async (object) => {
  const filePath = object.name ?? ''

  // Only handle files under /imports/
  if (!filePath.startsWith('imports/') || !filePath.endsWith('.csv')) return

  const parts = filePath.split('/')
  if (parts.length < 3) return
  const voyageId = parts[1]

  const bucket = storage.bucket(object.bucket)
  const [fileContent] = await bucket.file(filePath).download()
  const csvText = fileContent.toString('utf-8')

  const parsed = Papa.parse<Record<string, string>>(csvText, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (h) => h.trim().toLowerCase().replace(/\s+/g, '_'),
  })

  if (parsed.errors.length > 0) {
    console.error('CSV parse errors:', parsed.errors)
  }

  const required = ['cabin_number', 'first_name', 'last_name']
  const headers = parsed.meta.fields ?? []
  const missing = required.filter((r) => !headers.includes(r))
  if (missing.length > 0) {
    console.error(`CSV missing required columns: ${missing.join(', ')}`)
    return
  }

  const BATCH_SIZE = 499
  let batch = db.batch()
  let count = 0

  for (const row of parsed.data) {
    const cabin = row.cabin_number?.trim()
    const firstName = row.first_name?.trim()
    const lastName = row.last_name?.trim()
    if (!cabin || !firstName || !lastName) continue

    // Use a deterministic doc ID to make imports idempotent
    const docId = `${cabin}_${firstName}_${lastName}`.replace(/[^a-zA-Z0-9_-]/g, '_')
    const ref = db.collection('voyages').doc(voyageId).collection('guests').doc(docId)

    batch.set(ref, { cabin_number: cabin, first_name: firstName, last_name: lastName }, { merge: true })
    count++

    if (count % BATCH_SIZE === 0) {
      await batch.commit()
      batch = db.batch()
    }
  }

  if (count % BATCH_SIZE !== 0) await batch.commit()

  console.log(`Imported ${count} guests for voyage ${voyageId} from ${filePath}`)
})
