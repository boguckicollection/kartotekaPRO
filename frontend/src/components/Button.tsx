import React from 'react'

type Props = React.PropsWithChildren<{
  variant?: 'filled' | 'outline' | 'ghost' | 'success'
  size?: 'sm' | 'md' | 'lg'
  onClick?: () => void
  disabled?: boolean
  style?: React.CSSProperties
}>

export default function Button({ children, variant='filled', size='md', onClick, disabled, style }: Props) {
  const base: React.CSSProperties = {
    borderRadius: 10,
    fontWeight: 700,
    border: '1px solid var(--border)',
    background: '#fff',
    padding: size==='lg' ? '12px 18px' : size==='sm' ? '6px 10px' : '10px 14px'
  }
  if (variant==='filled') {
    base.background = 'var(--primary)'
    base.border = '1px solid var(--primary)'
    base.color = '#fff'
  } else if (variant==='success') {
    base.background = 'var(--success)'
    base.border = '1px solid var(--success)'
    base.color = '#fff'
  } else if (variant==='ghost') {
    base.background = 'transparent'
  }
  return <button onClick={onClick} disabled={disabled} style={{...base, opacity: disabled?0.6:1, ...style}}>{children}</button>
}

