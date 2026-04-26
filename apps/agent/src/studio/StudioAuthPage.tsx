import { useMemo, useState } from "react";
import { Eye, EyeSlash, CircleNotch, Sparkle } from "@phosphor-icons/react";
import { Button } from "@/studio/components/ui/button";
import { Input } from "@/studio/components/ui/input";
import { Label } from "@/studio/components/ui/label";
import { signIn } from "@/studio/hooks/useAuth";

export function StudioAuthPage({
  onAuthenticated,
}: {
  onAuthenticated: () => void;
}) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const headline = useMemo(
    () => (mode === "signin" ? "Welcome back" : "Create your workspace"),
    [mode],
  );

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading) {
      return;
    }

    if (!email.includes("@")) {
      setError("Enter a valid email.");
      return;
    }

    if (password.trim().length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setError(null);
    setLoading(true);
    await new Promise((resolve) => window.setTimeout(resolve, 300));
    signIn(email);
    setLoading(false);
    onAuthenticated();
  };

  return (
    <div className="min-h-screen grid place-items-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-8">
          <div className="size-7 rounded bg-primary text-primary-foreground grid place-items-center font-display text-[13px]">
            A
          </div>
          <span className="font-display text-[15px] tracking-tight">
            Apriori
          </span>
        </div>

        <h1 className="font-serif text-[24px] leading-tight mb-1.5">
          {headline}
        </h1>
        <p className="text-[13px] text-muted-foreground mb-6">
          {mode === "signin"
            ? "Sign in to open the Apriori workspace preview."
            : "Create a local preview session for Apriori on this device."}
        </p>

        <form onSubmit={submit} className="space-y-3.5">
          <div className="space-y-1.5">
            <Label htmlFor="studio-email" className="text-[12px]">
              Email
            </Label>
            <Input
              id="studio-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              disabled={loading}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="studio-password" className="text-[12px]">
              Password
            </Label>
            <div className="relative">
              <Input
                id="studio-password"
                type={showPassword ? "text" : "password"}
                autoComplete={
                  mode === "signin" ? "current-password" : "new-password"
                }
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                disabled={loading}
                className="pr-9"
              />
              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                className="absolute right-2 top-1/2 -translate-y-1/2 size-6 grid place-items-center text-muted-foreground hover:text-foreground transition-colors rounded"
                aria-label={showPassword ? "Hide password" : "Show password"}
                tabIndex={-1}
              >
                {showPassword ? (
                  <EyeSlash className="size-3.5" />
                ) : (
                  <Eye className="size-3.5" />
                )}
              </button>
            </div>
          </div>

          {error ? (
            <p className="text-[12px] text-destructive">{error}</p>
          ) : null}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <CircleNotch className="size-4 animate-spin" />
                Opening studio…
              </span>
            ) : mode === "signin" ? (
              "Sign in"
            ) : (
              "Create account"
            )}
          </Button>
        </form>

        <button
          type="button"
          onClick={() =>
            setMode((current) => (current === "signin" ? "signup" : "signin"))
          }
          className="mt-5 text-[12px] text-muted-foreground hover:text-foreground transition-colors w-full text-center"
          disabled={loading}
        >
          {mode === "signin"
            ? "No account? Create one →"
            : "Already have an account? Sign in →"}
        </button>

        <div className="mt-10 flex items-center gap-1.5 justify-center text-[11px] text-muted-foreground">
          <Sparkle className="size-3 text-clay" />
          <span>Local preview session only. No hosted auth is required here.</span>
        </div>
      </div>
    </div>
  );
}
