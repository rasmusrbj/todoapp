"use client"

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import {
  faCircleCheck,
  faCircleInfo,
  faCircleXmark,
  faSpinner,
  faTriangleExclamation,
} from "@fortawesome/pro-solid-svg-icons"
import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = ({ theme: themeProp, ...props }: ToasterProps) => {
  const { theme: resolvedTheme = "system" } = useTheme()
  const rawTheme = themeProp ?? resolvedTheme
  const DARK_THEMES = new Set(["dark", "slate"])
  const LIGHT_THEMES = new Set(["light", "warm", "stone"])
  const appliedTheme = (DARK_THEMES.has(rawTheme) ? "dark" : LIGHT_THEMES.has(rawTheme) ? "light" : rawTheme) as "system" | "light" | "dark"

  return (
    <Sonner
      theme={appliedTheme}
      className="toaster group"
      duration={4000}
      visibleToasts={3}
      icons={{
        success: <FontAwesomeIcon icon={faCircleCheck} className="size-4" />,
        info: <FontAwesomeIcon icon={faCircleInfo} className="size-4" />,
        warning: <FontAwesomeIcon icon={faTriangleExclamation} className="size-4" />,
        error: <FontAwesomeIcon icon={faCircleXmark} className="size-4" />,
        loading: <FontAwesomeIcon icon={faSpinner} className="size-4 animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
