import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Users, UserPlus, Shield, Mail, Clock,
  X, AlertTriangle, ChevronDown, Send,
} from 'lucide-react'
import { team } from '@/lib/api'
import type { TeamMember, TeamInvitation } from '@/lib/api'

interface TeamPageProps {
  readonly onError: (msg: string) => void
}

const ROLES = [
  { value: 'pi', label: 'PI', level: 0 },
  { value: 'admin', label: 'Admin', level: 1 },
  { value: 'postdoc', label: 'Postdoc', level: 2 },
  { value: 'grad_student', label: 'Grad Student', level: 3 },
  { value: 'tech', label: 'Tech', level: 3 },
  { value: 'undergrad', label: 'Undergrad', level: 4 },
  { value: 'visitor', label: 'Visitor', level: 4 },
]

function roleBadge(role: string) {
  const colors: Record<string, string> = {
    pi: 'bg-blue-100 text-blue-700',
    admin: 'bg-purple-100 text-purple-700',
    postdoc: 'bg-green-100 text-green-700',
    grad_student: 'bg-amber-100 text-amber-700',
    tech: 'bg-teal-100 text-teal-700',
    undergrad: 'bg-gray-100 text-gray-600',
    visitor: 'bg-gray-100 text-gray-500',
  }
  const label = ROLES.find((r) => r.value === role)?.label ?? role
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded-full ${colors[role] ?? 'bg-gray-100 text-gray-600'}`}
    >
      <Shield className="size-3" />
      {label}
    </span>
  )
}


/* ---------- Invite Form ---------- */

function InviteForm({
  onSuccess,
  onError,
}: {
  readonly onSuccess: () => void
  readonly onError: (msg: string) => void
}) {
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState('grad_student')

  const mutation = useMutation({
    mutationFn: () => team.invite({ email, name, role }),
    onSuccess: () => {
      setEmail('')
      setName('')
      setRole('grad_student')
      onSuccess()
    },
    onError: (err: Error) => onError(err.message),
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        mutation.mutate()
      }}
      className="flex flex-col sm:flex-row items-end gap-3"
    >
      <div className="flex-1 w-full">
        <label htmlFor="invite-name" className="block text-sm font-medium text-gray-700 mb-1">
          Name
        </label>
        <input
          id="invite-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Jane Doe"
          required
          className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
        />
      </div>
      <div className="flex-1 w-full">
        <label htmlFor="invite-email" className="block text-sm font-medium text-gray-700 mb-1">
          Email
        </label>
        <input
          id="invite-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="jane@lab.edu"
          required
          className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
        />
      </div>
      <div className="w-full sm:w-40">
        <label htmlFor="invite-role" className="block text-sm font-medium text-gray-700 mb-1">
          Role
        </label>
        <div className="relative">
          <select
            id="invite-role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm appearance-none bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary pr-8"
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 size-4 text-gray-400 pointer-events-none" />
        </div>
      </div>
      <button
        type="submit"
        disabled={mutation.isPending || !email || !name}
        className="flex items-center gap-2 px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
      >
        <Send className="size-4" />
        {mutation.isPending ? 'Sending...' : 'Send Invite'}
      </button>
    </form>
  )
}

/* ---------- Role Selector ---------- */

function RoleSelector({
  memberId,
  currentRole,
  onSuccess,
  onError,
}: {
  readonly memberId: number
  readonly currentRole: string
  readonly onSuccess: () => void
  readonly onError: (msg: string) => void
}) {
  const mutation = useMutation({
    mutationFn: (newRole: string) => team.updateRole(memberId, newRole),
    onSuccess,
    onError: (err: Error) => onError(err.message),
  })

  return (
    <div className="relative">
      <select
        value={currentRole}
        onChange={(e) => mutation.mutate(e.target.value)}
        disabled={mutation.isPending}
        className="px-2 py-1 border border-gray-200 rounded-md text-xs appearance-none bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary pr-6 disabled:opacity-50"
      >
        {ROLES.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-1 top-1/2 -translate-y-1/2 size-3 text-gray-400 pointer-events-none" />
    </div>
  )
}

/* ---------- Main Component ---------- */

export function TeamPage({ onError }: Readonly<TeamPageProps>) {
  const queryClient = useQueryClient()
  const [confirmDeactivate, setConfirmDeactivate] = useState<number | null>(null)

  const { data: membersData, isLoading: loadingMembers } = useQuery({
    queryKey: ['team-members'],
    queryFn: () => team.list(),
  })

  const { data: invitationsData, isLoading: loadingInvitations } = useQuery({
    queryKey: ['team-invitations'],
    queryFn: () => team.listInvitations(),
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: number) => team.deactivate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team-members'] })
      setConfirmDeactivate(null)
    },
    onError: (err: Error) => onError(err.message),
  })

  const cancelInviteMutation = useMutation({
    mutationFn: (id: number) => team.cancelInvitation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team-invitations'] })
    },
    onError: (err: Error) => onError(err.message),
  })

  const refreshAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['team-members'] })
    queryClient.invalidateQueries({ queryKey: ['team-invitations'] })
  }, [queryClient])

  const members: TeamMember[] = membersData?.items ?? []
  const invitations: TeamInvitation[] = invitationsData?.items ?? []
  const pendingInvitations = invitations.filter((i) => i.status === 'pending')

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Invite Section */}
      <div className="border border-gray-200 rounded-xl p-6 shadow-sm bg-white">
        <div className="flex items-center gap-3 mb-6">
          <div className="size-9 flex items-center justify-center rounded-lg bg-primary/10">
            <UserPlus className="size-5 text-primary" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">Invite Team Member</h3>
        </div>
        <InviteForm onSuccess={refreshAll} onError={onError} />
      </div>

      {/* Members Table */}
      <div className="border border-gray-200 rounded-xl shadow-sm bg-white overflow-hidden">
        <div className="flex items-center gap-3 p-6 pb-4">
          <div className="size-9 flex items-center justify-center rounded-lg bg-primary/10">
            <Users className="size-5 text-primary" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">
            Team Members
            {members.length > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-400">({members.length})</span>
            )}
          </h3>
        </div>

        {loadingMembers ? (
          <div className="p-8 text-center text-sm text-gray-400">Loading members...</div>
        ) : members.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">No team members yet</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-b border-gray-100 bg-gray-50/50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-600">Name</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-600">Email</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-600">Role</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-600">Status</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                    <td className="px-6 py-3">
                      <div className="flex items-center gap-3">
                        <div className="size-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                          <span className="text-xs font-bold text-primary">
                            {m.name.charAt(0).toUpperCase()}
                          </span>
                        </div>
                        <span className="font-medium text-gray-900">{m.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-3 text-gray-500">
                      {m.email ? (
                        <span className="flex items-center gap-1">
                          <Mail className="size-3 text-gray-400" />
                          {m.email}
                        </span>
                      ) : (
                        <span className="text-gray-300">--</span>
                      )}
                    </td>
                    <td className="px-6 py-3">
                      <RoleSelector
                        memberId={m.id}
                        currentRole={m.role}
                        onSuccess={() =>
                          queryClient.invalidateQueries({ queryKey: ['team-members'] })
                        }
                        onError={onError}
                      />
                    </td>
                    <td className="px-6 py-3">
                      {m.is_active ? (
                        <span className="inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-full bg-green-100 text-green-700">
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-full bg-gray-100 text-gray-500">
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-right">
                      {m.is_active && confirmDeactivate === m.id ? (
                        <div className="flex items-center justify-end gap-2">
                          <span className="text-xs text-red-500">Confirm?</span>
                          <button
                            onClick={() => deactivateMutation.mutate(m.id)}
                            disabled={deactivateMutation.isPending}
                            className="px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
                          >
                            Yes
                          </button>
                          <button
                            onClick={() => setConfirmDeactivate(null)}
                            className="px-2 py-1 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                          >
                            No
                          </button>
                        </div>
                      ) : m.is_active ? (
                        <button
                          onClick={() => setConfirmDeactivate(m.id)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs text-red-500 hover:bg-red-50 rounded transition-colors"
                        >
                          <AlertTriangle className="size-3" />
                          Deactivate
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pending Invitations */}
      <div className="border border-gray-200 rounded-xl shadow-sm bg-white overflow-hidden">
        <div className="flex items-center gap-3 p-6 pb-4">
          <div className="size-9 flex items-center justify-center rounded-lg bg-amber-50">
            <Clock className="size-5 text-amber-600" />
          </div>
          <h3 className="text-lg font-bold text-gray-900">
            Pending Invitations
            {pendingInvitations.length > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                ({pendingInvitations.length})
              </span>
            )}
          </h3>
        </div>

        {loadingInvitations ? (
          <div className="p-8 text-center text-sm text-gray-400">Loading invitations...</div>
        ) : pendingInvitations.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">No pending invitations</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-b border-gray-100 bg-gray-50/50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-600">Name</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-600">Email</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-600">Role</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-600">Sent</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingInvitations.map((inv) => (
                  <tr key={inv.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                    <td className="px-6 py-3 font-medium text-gray-900">{inv.name}</td>
                    <td className="px-6 py-3 text-gray-500">{inv.email}</td>
                    <td className="px-6 py-3">{roleBadge(inv.role)}</td>
                    <td className="px-6 py-3 text-gray-400 text-xs">
                      {inv.created_at
                        ? new Date(inv.created_at).toLocaleDateString()
                        : '--'}
                    </td>
                    <td className="px-6 py-3 text-right">
                      <button
                        onClick={() => cancelInviteMutation.mutate(inv.id)}
                        disabled={cancelInviteMutation.isPending}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-red-500 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                      >
                        <X className="size-3" />
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
