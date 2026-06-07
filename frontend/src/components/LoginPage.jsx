import { useState } from "react";

const DEMO_CREDENTIALS = {
  email: "alexhales@gmail.com",
  password: "test1234",
};

const UNIVERSITIES = [
  "University of Florida",
  "Florida State University",
  "University of Central Florida",
  "Other",
];

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [university, setUniversity] = useState(UNIVERSITIES[0]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    setTimeout(() => {
      const emailNorm = email.trim().toLowerCase();
      if (
        emailNorm === DEMO_CREDENTIALS.email &&
        password === DEMO_CREDENTIALS.password &&
        university
      ) {
        sessionStorage.setItem(
          "advisor_auth",
          JSON.stringify({ email: emailNorm, university })
        );
        onLogin({ email: emailNorm, university });
      } else {
        setError("Invalid email or password. Use the demo credentials below.");
      }
      setLoading(false);
    }, 400);
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-zinc-950 px-4">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900/80 p-8 shadow-xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/20">
            <div className="h-3 w-3 rounded-full bg-emerald-500" />
          </div>
          <h1 className="text-2xl font-semibold text-zinc-100">Academic Advisor</h1>
          <p className="mt-2 text-sm text-zinc-500">
            Sign in to access your AI degree planning assistant
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1.5 block text-xs font-medium text-zinc-400">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition-colors focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
              placeholder="you@university.edu"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-zinc-400">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition-colors focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
              placeholder="••••••••"
            />
          </div>

          <div>
            <label htmlFor="university" className="mb-1.5 block text-xs font-medium text-zinc-400">
              University
            </label>
            <select
              id="university"
              value={university}
              onChange={(e) => setUniversity(e.target.value)}
              required
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition-colors focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
            >
              {UNIVERSITIES.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>

          {error && (
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full cursor-pointer rounded-lg bg-emerald-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-zinc-600">
          Demo: alexhales@gmail.com / test1234
        </p>
      </div>
    </div>
  );
}
