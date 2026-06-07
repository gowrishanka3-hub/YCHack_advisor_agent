export default function GraduationPlanTable({ plan }) {
  if (!plan?.semesters?.length) return null;

  return (
    <div className="mt-2 overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900/80">
      <div className="border-b border-zinc-700 px-4 py-2 text-xs font-medium uppercase tracking-wider text-zinc-400">
        Graduation Plan
        {plan.credits_remaining > 0 && (
          <span className="ml-2 text-zinc-500">
            · {plan.credits_remaining} credits remaining
          </span>
        )}
      </div>
      <div className="divide-y divide-zinc-800">
        {plan.semesters.map((semester) => (
          <div key={semester.term} className="px-4 py-3">
            <div className="mb-2 text-sm font-semibold text-zinc-200">
              {semester.term}
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-500">
                  <th className="pb-1 pr-4 font-medium">Course</th>
                  <th className="pb-1 pr-4 font-medium">Title</th>
                  <th className="pb-1 font-medium">Credits</th>
                </tr>
              </thead>
              <tbody>
                {semester.courses.map((course) => (
                  <tr key={course.id} className="text-zinc-300">
                    <td className="py-1 pr-4 font-mono text-xs text-zinc-400">
                      {course.id}
                    </td>
                    <td className="py-1 pr-4">{course.title}</td>
                    <td className="py-1 text-zinc-500">{course.credits}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
