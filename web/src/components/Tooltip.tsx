import { Children, cloneElement, type FocusEvent, type ReactElement, useId, useState } from 'react'

export function Tooltip({ children, label }: { children: ReactElement; label: string }) {
  const id = useId()
  const [show, setShow] = useState(false)
  const child = Children.only(children) as ReactElement<
    React.HTMLAttributes<HTMLElement> & { children?: React.ReactNode }
  >

  return cloneElement(
    child,
    {
      'aria-describedby': show ? id : undefined,
      onMouseEnter: (e: React.MouseEvent<HTMLElement>) => {
        setShow(true)
        child.props.onMouseEnter?.(e)
      },
      onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
        setShow(false)
        child.props.onMouseLeave?.(e)
      },
      onFocus: (e: FocusEvent<HTMLElement>) => {
        setShow(true)
        child.props.onFocus?.(e)
      },
      onBlur: (e: FocusEvent<HTMLElement>) => {
        setShow(false)
        child.props.onBlur?.(e)
      }
    },
    ...(child.props.children ? Children.toArray(child.props.children) : []),
    <span key={`${id}-bubble`} id={id} className={`tooltip-bubble${show ? ' is-visible' : ''}`} role="tooltip">
      {label}
    </span>
  )
}
