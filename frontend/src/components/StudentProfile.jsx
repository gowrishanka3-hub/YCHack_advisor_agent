import { useEffect, useState } from "react";

const EMPTY_STUDENT = {
  name: "Your Name",
  major: "Undeclared",
  year: "—",
  gpa: null,
  credits_earned: 0,
  credits_total: 120,
  categories: {},
};

export default function StudentProfile() {
  const [student, setStudent] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/data/degree_audit.json")
      .then((r) => r.json())
      .then((data) => {
        setStudent(data.length > 0 ? data[0] : null);
      })
      .catch(() => setStudent(null))
      .finally(() => setLoading(false));
  }, []);

  const s = student ?? EMPTY_STUDENT;
  const creditsEarned = s.credits_earned ?? 0;
  const creditsTotal = s.credits_total ?? 120;
  const creditsRemaining = Math.max(0, creditsTotal - creditsEarned);
  const progress = creditsTotal > 0 ? (creditsEarned / creditsTotal) * 100 : 0;
  const categories = s.categories ?? {};
  const isEmpty = !student;

  return (
    <div className="flex h-full flex-col rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
      <div className="mb-1 text-xs font-medium uppercase tracking-wider text-zinc-500">
        Student Profile
      </div>

      {loading ? (
        <div className="text-sm text-zinc-500">Loading...</div>
      ) : (
        <>
          <h2 className="text-lg font-semibold text-zinc-100">{s.name}</h2>
          <p className="mt-1 text-sm text-zinc-400">
            {s.major} · {s.year}
          </p>
          {s.gpa != null && (
            <p className="mt-1 text-sm text-zinc-400">GPA {s.gpa}</p>
          )}

          {isEmpty && (
            <p className="mt-3 rounded-md border border-dashed border-zinc-700 px-3 py-2 text-xs text-zinc-500">
              Add student data to data/degree_audit.json
            </p>
          )}

          <div className="mt-5">
            <div className="mb-1 flex justify-between text-xs text-zinc-500">
              <span>Degree progress</span>
              <span>
                {creditsEarned} / {creditsTotal} credits
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          <div className="mt-5 space-y-3">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2">
              <div className="text-xs text-zinc-500">Credits remaining</div>
              <div className="text-xl font-semibold text-zinc-100">
                {creditsRemaining}
              </div>
            </div>

            {Object.keys(categories).length > 0 ? (
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">
                  By category
                </div>
                {Object.entries(categories).map(([cat, info]) => (
                  <div
                    key={cat}
                    className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2"
                  >
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-300">{cat}</span>
                      <span className="text-zinc-500">
                        {info.earned ?? 0}/{info.required ?? 0}
                      </span>
                    </div>
                    {(info.courses_remaining?.length ?? 0) > 0 && (
                      <div className="mt-1 text-xs text-zinc-500">
                        {info.courses_remaining.length} course
                        {info.courses_remaining.length !== 1 ? "s" : ""} left
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              !isEmpty && (
                <p className="text-xs text-zinc-500">No category breakdown yet.</p>
              )
            )}
          </div>
        </>
      )}
    </div>
  );
}
