import * as functions from 'firebase-functions'
import * as admin from 'firebase-admin'

if (!admin.apps.length) admin.initializeApp()

const db = admin.firestore()

/**
 * Callable function: marks a voyage as archived and sets a new voyage as current.
 * Old voyage data is preserved for audit purposes.
 */
export const archiveVoyage = functions.https.onCall(async (data, context) => {
  if (context.auth?.token?.role !== 'admin') {
    throw new functions.https.HttpsError('permission-denied', 'Admins only.')
  }

  const { voyageId, newVoyageId } = data as { voyageId: string; newVoyageId: string }
  if (!voyageId || !newVoyageId) {
    throw new functions.https.HttpsError('invalid-argument', 'voyageId and newVoyageId are required.')
  }

  const batch = db.batch()

  batch.update(db.collection('voyages').doc(voyageId), {
    is_current: false,
    archived_at: admin.firestore.FieldValue.serverTimestamp(),
  })

  batch.update(db.collection('voyages').doc(newVoyageId), { is_current: true })

  batch.update(db.collection('appConfig').doc('settings'), {
    current_voyage_id: newVoyageId,
  })

  await batch.commit()

  return { success: true }
})
