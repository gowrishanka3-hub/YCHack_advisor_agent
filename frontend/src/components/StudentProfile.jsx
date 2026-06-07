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

const QUICK_ACTIONS = [
  {
    label: "Next semester",
    question: "What courses should I take next semester?",
  },
  {
    label: "Critical tracking",
    question: "Am I on track for critical tracking?",
  },
  {
    label: "Graduation plan",
    question: "Build me a graduation plan",
  },
];

function formatCategoryName(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function StudentProfile({ onAskAdvisor }) {
  const [student, setStudent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedCategory, setExpandedCategory] = useState(null);

  useEffect(() => {
    fetch("/data/degree_audit.json")
      .then((r) => r.json())
      .then((data) => {
        setStudent(data.length > 0 ? data[0] : null);
      })
      .catch(() => setStudent(null))
      .finally(() => setLoading(false));
  }, []);

  const handleAsk = (question) => {
    if (onAskAdvisor) onAskAdvisor(question);
  };

  const s = student ?? EMPTY_STUDENT;
  const creditsEarned = s.credits_earned ?? 0;
  const creditsTotal = s.credits_total ?? 120;
  const creditsRemaining = Math.max(0, creditsTotal - creditsEarned);
  const progress = creditsTotal > 0 ? (creditsEarned / creditsTotal) * 100 : 0;
  const categories = s.categories ?? {};
  const isEmpty = !student;
  const ctStatus = s.critical_tracking_status;
  const nextRec = s.next_semester_recommendation;

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

          {ctStatus && (
            <button
              type="button"
              onClick={() =>
                handleAsk("Am I on track for critical tracking? What do I still need?")
              }
              className="mt-3 w-full cursor-pointer rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-left text-sm text-emerald-200 transition-colors hover:border-emerald-500/50 hover:bg-emerald-500/20"
            >
              <span className="text-xs uppercase tracking-wider text-emerald-400/80">
                Critical tracking
              </span>
              <div className="font-medium">{ctStatus}</div>
            </button>
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
            <button
              type="button"
              onClick={() =>
                handleAsk(
                  `What courses should I take ${nextRec?.term ? `in ${nextRec.term}` : "next semester"}?`
                )
              }
              className="w-full cursor-pointer rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-left transition-colors hover:border-zinc-600 hover:bg-zinc-900"
            >
              <div className="text-xs text-zinc-500">Credits remaining</div>
              <div className="text-xl font-semibold text-zinc-100">
                {creditsRemaining}
              </div>
            </button>

            {nextRec?.courses?.length > 0 && (
              <button
                type="button"
                onClick={() =>
                  handleAsk(
                    `Tell me about my recommended courses for ${nextRec.term}: ${nextRec.courses.join(", ")}`
                  )
                }
                className="w-full cursor-pointer rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2 text-left transition-colors hover:border-zinc-500 hover:bg-zinc-900"
              >
                <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">
                  {nextRec.term} recommendation
                </div>
                <div className="mt-1 text-xs text-zinc-400">
                  {nextRec.courses.join(", ")}
                </div>
              </button>
            )}

            {Object.keys(categories).length > 0 ? (
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">
                  By category
                </div>
                {Object.entries(categories).map(([cat, info]) => {
                  const isExpanded = expandedCategory === cat;
                  const remaining = info.courses_remaining ?? [];
                  return (
                    <div
                      key={cat}
                      className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/50"
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedCategory(isExpanded ? null : cat)
                        }
                        className="flex w-full cursor-pointer items-center justify-between px-3 py-2 text-left transition-colors hover:bg-zinc-900"
                      >
                        <span className="text-sm text-zinc-300">
                          {formatCategoryName(cat)}
                        </span>
                        <span className="text-zinc-500">
                          {info.earned ?? 0}/{info.required ?? 0}
                          <span className="ml-1 text-xs">{isExpanded ? "▾" : "▸"}</span>
                        </span>
                      </button>
                      {isExpanded && (
                        <div className="border-t border-zinc-800 px-3 py-2">
                          {remaining.length > 0 ? (
                            <ul className="space-y-1 text-xs text-zinc-400">
                              {remaining.map((course) => (
                                <li key={course}>{course}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-xs text-zinc-500">No courses remaining</p>
                          )}
                          {info.notes && (
                            <p className="mt-2 text-xs text-zinc-500">{info.notes}</p>
                          )}
                          <button
                            type="button"
                            onClick={() =>
                              handleAsk(
                                `What do I still need for ${formatCategoryName(cat)}? I have ${remaining.length} courses left.`
                              )
                            }
                            className="mt-2 cursor-pointer text-xs text-emerald-400 hover:text-emerald-300"
                          >
                            Ask advisor about this →
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              !isEmpty && (
                <p className="text-xs text-zinc-500">No category breakdown yet.</p>
              )
            )}
          </div>

          <div className="mt-5 space-y-2 border-t border-zinc-800 pt-4">
            <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              Quick ask
            </div>
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.label}
                type="button"
                onClick={() => handleAsk(action.question)}
                className="w-full cursor-pointer rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-left text-sm text-zinc-300 transition-colors hover:border-emerald-500/40 hover:bg-zinc-800 hover:text-zinc-100"
              >
                {action.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
