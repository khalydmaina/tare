import { Link, useLocation } from 'react-router-dom'

export function Nav() {
  const { pathname } = useLocation()
  const onApp = pathname.startsWith('/app')

  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-canvas/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-4 md:px-6">
        <Link to="/" className="flex items-center gap-3">
          <img src="/brand/tare-mark.svg" alt="" className="h-8 w-8" />
          <span className="tare-wordmark text-[1.35rem] text-white">tare</span>
        </Link>

        <nav className="hidden items-center gap-7 text-sm text-mute md:flex">
          <a href="/#how" className="transition hover:text-ink">
            How it works
          </a>
          <a href="/#proof" className="transition hover:text-ink">
            Proof
          </a>
          <a href="/#attacks" className="transition hover:text-ink">
            Attack Lab
          </a>
          <Link
            to="/app"
            className={`transition hover:text-ink ${onApp ? 'text-ink' : ''}`}
          >
            Flight Recorder
          </Link>
        </nav>

        <Link
          to="/app"
          className="rounded-[4px] border border-line-strong bg-elevated px-3.5 py-2 text-sm font-medium text-ink transition hover:border-ink/40 active:scale-[0.98]"
        >
          Open recorder
        </Link>
      </div>
    </header>
  )
}
