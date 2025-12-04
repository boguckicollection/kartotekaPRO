import React from 'react'

export default function Card({children, style}:{children: React.ReactNode, style?: React.CSSProperties}){
  return <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.05)', ...style }}>{children}</div>
}

