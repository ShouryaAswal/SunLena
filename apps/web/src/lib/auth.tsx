import { onAuthStateChanged, signInWithPopup, signInWithRedirect, signOut, type User } from 'firebase/auth'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { firebaseAuth, firebaseConfigured, googleProvider } from './firebase'

type AuthValue = {
  user: User | null
  ready: boolean
  configured: boolean
  signIn: () => Promise<void>
  signOutUser: () => Promise<void>
  getToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(!firebaseAuth)

  useEffect(() => {
    if (!firebaseAuth) return
    return onAuthStateChanged(firebaseAuth, (nextUser) => {
      setUser(nextUser)
      setReady(true)
    })
  }, [])

  const value = useMemo<AuthValue>(() => ({
    user,
    ready,
    configured: firebaseConfigured,
    signIn: async () => {
      if (!firebaseAuth) throw new Error('Google sign-in needs the Firebase settings in your .env file.')
      if (window.matchMedia('(max-width: 700px)').matches) {
        await signInWithRedirect(firebaseAuth, googleProvider)
      } else {
        await signInWithPopup(firebaseAuth, googleProvider)
      }
    },
    signOutUser: async () => {
      if (firebaseAuth) await signOut(firebaseAuth)
    },
    getToken: async () => user ? user.getIdToken() : null,
  }), [user, ready])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider.')
  return value
}
