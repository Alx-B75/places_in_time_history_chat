import React, { createContext, useContext, useState } from 'react'

const InteractionContext = createContext(null)

export function InteractionProvider({ children }){
  const [mode, setMode] = useState('Student')
  const value = { mode, setMode }
  return (
    <InteractionContext.Provider value={value}>
      {children}
    </InteractionContext.Provider>
  )
}

export function useInteraction(){
  const ctx = useContext(InteractionContext)
  if(!ctx) throw new Error('useInteraction must be used within InteractionProvider')
  return ctx
}

export default InteractionContext
