import { useState, type FormEvent } from 'react'
import { ArrowRight, Eye, EyeOff, Loader2 } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { authenticateLocalCredentials, signIn } from '../hooks/useAuth'

export function AuthPage() {
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (loading) {
      return
    }

    if (identifier.trim().length < 2) {
      setError('Enter a username.')
      return
    }

    const authenticatedIdentifier = authenticateLocalCredentials(identifier, password)
    if (!authenticatedIdentifier) {
      setError('Invalid username or password.')
      return
    }

    setError(null)
    setLoading(true)
    await new Promise((resolve) => window.setTimeout(resolve, 240))
    signIn(authenticatedIdentifier)
    setLoading(false)
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-background px-6 py-10">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(70,118,255,0.08),_transparent_34%),radial-gradient(circle_at_bottom_right,_rgba(70,118,255,0.06),_transparent_30%)]"
      />

      <div className="relative mx-auto flex min-h-[calc(100vh-5rem)] max-w-xl items-center justify-center">
        <Card className="w-full rounded-[28px] border border-border bg-card/95 shadow-sm">
          <CardHeader className="space-y-4 p-7 pb-5 md:p-8 md:pb-5">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-primary/75">
                Silico Apriori: Agentic Method Development
              </p>
              <CardTitle className="mt-3 text-3xl">Sign in</CardTitle>
            </div>
          </CardHeader>

          <CardContent className="p-7 pt-0 md:p-8 md:pt-0">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="agent-username"
                  className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground"
                >
                  Username
                </label>
                <Input
                  id="agent-username"
                  type="text"
                  autoComplete="username"
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  placeholder="lab-operator"
                  disabled={loading}
                  autoFocus
                />
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="agent-password"
                  className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground"
                >
                  Password
                </label>
                <div className="relative">
                  <Input
                    id="agent-password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Enter password"
                    disabled={loading}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    className="absolute right-2 top-1/2 inline-flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>

              {error ? <p className="text-sm text-destructive">{error}</p> : null}

              <Button type="submit" size="lg" className="mt-2 w-full rounded-xl" disabled={loading}>
                {loading ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="size-4 animate-spin" />
                    Opening workspace
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    Continue to agent
                    <ArrowRight className="size-4" />
                  </span>
                )}
              </Button>
            </form>

            <p className="mt-5 text-sm leading-6 text-muted-foreground">
              <a
                href="mailto:hello@silico-labs.com?subject=Apriori%20Login%20Credentials"
                className="font-semibold text-primary underline underline-offset-4 transition-colors hover:text-primary/80"
              >
                Contact us
              </a>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
