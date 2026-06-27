import * as functions from 'firebase-functions'
import * as admin from 'firebase-admin'

if (!admin.apps.length) admin.initializeApp()

/**
 * Callable function: admin assigns a role to a user.
 * Sets a Firebase Auth custom claim so Firestore Security Rules can enforce it.
 */
export const setUserRole = functions.https.onCall(async (data, context) => {
  // Only admins can call this
  if (!context.auth?.token?.role || context.auth.token.role !== 'admin') {
    throw new functions.https.HttpsError('permission-denied', 'Only admins can assign roles.')
  }

  const { uid, role } = data as { uid: string; role: string }
  const validRoles = ['admin', 'restaurant', 'galley']
  if (!uid || !validRoles.includes(role)) {
    throw new functions.https.HttpsError('invalid-argument', 'Invalid uid or role.')
  }

  await admin.auth().setCustomUserClaims(uid, { role })

  // Mirror role in Firestore user document
  await admin.firestore().collection('users').doc(uid).set({ role }, { merge: true })

  return { success: true }
})
