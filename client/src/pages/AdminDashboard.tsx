import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { accounts, AccountApiError } from "../api/accounts.ts";

type User = { id: number; username: string; email: string | null; is_active: boolean };
type Group = { id: number; name: string };
type Req = {
  id: number;
  code: string;
  user_id: number;
  username: string | null;
  status: string;
};

export default function AdminDashboard() {
  const [ready, setReady] = useState(false);
  const [denied, setDenied] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [requests, setRequests] = useState<Req[]>([]);
  const [newGroup, setNewGroup] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  async function refresh(): Promise<void> {
    setUsers(await accounts.listUsers());
    setGroups(await accounts.listGroups());
    setRequests(await accounts.listRequests());
  }

  useEffect(() => {
    void (async () => {
      try {
        const me = await accounts.me();
        if (!me.is_admin) {
          setDenied(true);
          return;
        }
        await refresh();
      } catch (err) {
        if (err instanceof AccountApiError && err.status === 401) {
          window.location.assign("/login?next=/admin");
          return;
        }
        setDenied(true);
      } finally {
        setReady(true);
      }
    })();
  }, []);

  async function guarded(fn: () => Promise<void>): Promise<void> {
    try {
      await fn();
      await refresh();
      setNotice(null);
    } catch (err) {
      setNotice(err instanceof AccountApiError ? err.message : "Action failed");
    }
  }

  if (!ready)
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-gray-400 animate-spin" />
      </div>
    );
  if (denied)
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <p className="text-red-600 dark:text-red-400">
          Admin privileges required.
        </p>
      </div>
    );

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-4xl mx-auto space-y-8">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">
          Admin
        </h1>
        {notice && (
          <p className="text-sm text-red-600 dark:text-red-400">{notice}</p>
        )}

        <section className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
          <h2 className="font-semibold mb-3 text-gray-800 dark:text-gray-100">
            Pending access requests
          </h2>
          {requests.filter((r) => r.status === "pending").length === 0 ? (
            <p className="text-sm text-gray-500">No pending requests.</p>
          ) : (
            <ul className="space-y-2">
              {requests
                .filter((r) => r.status === "pending")
                .map((r) => (
                  <li
                    key={r.id}
                    className="flex items-center justify-between text-sm text-gray-700 dark:text-gray-200"
                  >
                    <span>
                      <strong>{r.username ?? `#${r.user_id ?? "?"}`}</strong>{" "}
                      → mount <code>{r.code}</code>
                    </span>
                    <span className="space-x-2">
                      <button
                        className="px-2 py-1 rounded bg-green-600 text-white"
                        onClick={() =>
                          void guarded(() =>
                            accounts
                              .resolveRequest(r.id, "approve", "read")
                              .then(() => undefined),
                          )
                        }
                      >
                        Approve (read)
                      </button>
                      <button
                        className="px-2 py-1 rounded bg-green-700 text-white"
                        onClick={() =>
                          void guarded(() =>
                            accounts
                              .resolveRequest(r.id, "approve", "write")
                              .then(() => undefined),
                          )
                        }
                      >
                        Approve (write)
                      </button>
                      <button
                        className="px-2 py-1 rounded bg-red-600 text-white"
                        onClick={() =>
                          void guarded(() =>
                            accounts
                              .resolveRequest(r.id, "deny", null)
                              .then(() => undefined),
                          )
                        }
                      >
                        Deny
                      </button>
                    </span>
                  </li>
                ))}
            </ul>
          )}
        </section>

        <section className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
          <h2 className="font-semibold mb-3 text-gray-800 dark:text-gray-100">
            Users
          </h2>
          <ul className="space-y-2">
            {users.map((u) => (
              <li
                key={u.id}
                className="flex items-center justify-between text-sm text-gray-700 dark:text-gray-200"
              >
                <span>
                  {u.username}{" "}
                  {!u.is_active && (
                    <span className="text-red-500">(disabled)</span>
                  )}
                </span>
                <button
                  className="px-2 py-1 rounded bg-gray-200 dark:bg-gray-700"
                  onClick={() =>
                    void guarded(() =>
                      accounts
                        .setUserActive(u.id, !u.is_active)
                        .then(() => undefined),
                    )
                  }
                >
                  {u.is_active ? "Disable" : "Enable"}
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
          <h2 className="font-semibold mb-3 text-gray-800 dark:text-gray-100">
            Groups
          </h2>
          <div className="flex gap-2 mb-3">
            <input
              className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
              placeholder="New group name"
              value={newGroup}
              onChange={(e) => setNewGroup(e.target.value)}
            />
            <button
              disabled={!newGroup}
              className="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm disabled:opacity-50"
              onClick={() =>
                void guarded(async () => {
                  await accounts.createGroup(newGroup);
                  setNewGroup("");
                })
              }
            >
              Create
            </button>
          </div>
          <ul className="space-y-2">
            {groups.map((g) => (
              <GroupRow key={g.id} group={g} onChange={() => void guarded(async () => {})} />
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

function GroupRow({
  group,
  onChange,
}: {
  group: Group;
  onChange: () => void;
}) {
  const [ref, setRef] = useState("");
  const [type, setType] = useState<"user" | "group">("user");
  const [msg, setMsg] = useState<string | null>(null);

  async function add(): Promise<void> {
    try {
      await accounts.addGroupMember(group.id, type, ref);
      setRef("");
      setMsg("Added");
      onChange();
    } catch (err) {
      setMsg(err instanceof AccountApiError ? err.message : "Failed");
    }
  }

  return (
    <li className="text-sm text-gray-700 dark:text-gray-200">
      <div className="flex items-center justify-between">
        <strong>{group.name}</strong>
        <button
          className="px-2 py-1 rounded bg-red-100 text-red-700"
          onClick={() =>
            void accounts.deleteGroup(group.id).then(onChange)
          }
        >
          Delete
        </button>
      </div>
      <div className="flex gap-2 mt-1">
        <select
          value={type}
          onChange={(e) => setType(e.target.value as "user" | "group")}
          className="rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1 text-xs"
        >
          <option value="user">user</option>
          <option value="group">group</option>
        </select>
        <input
          className="flex-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1 text-xs"
          placeholder="username or group name"
          value={ref}
          onChange={(e) => setRef(e.target.value)}
        />
        <button
          disabled={!ref}
          className="px-2 py-1 rounded bg-blue-600 text-white text-xs disabled:opacity-50"
          onClick={() => void add()}
        >
          Add member
        </button>
      </div>
      {msg && <p className="text-xs text-gray-500 mt-1">{msg}</p>}
    </li>
  );
}
