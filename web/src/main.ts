import "./styles.css";

// --- TYPES & INTERFACES ---
type User = { id: string; username: string; display_name: string; email: string };
type Project = { id: string; key: string; name: string };
type Sprint = {
  id: string;
  project_id: string;
  name: string;
  start_date: string | null;
  end_date: string | null;
  status: "planned" | "active" | "completed";
  completed_at: string | null;
};
type Issue = {
  id: string;
  issue_key: string;
  project_id: string;
  type: "epic" | "story" | "task" | "bug" | "sub_task";
  title: string;
  description: string | null;
  status: string;
  priority: string;
  assignee: User | null;
  reporter: User;
  sprint: Sprint | null;
  parent_id: string | null;
  labels: string[];
  story_points: number | null;
  watchers: string[];
  version: number;
  created_at: string;
  updated_at: string;
};
type BoardColumn = { status: { name: string; is_done: boolean }; issues: Issue[] };
type Board = { project: Project; columns: BoardColumn[] };
type Comment = {
  id: string;
  issue_id: string;
  author: User;
  parent_id: string | null;
  body: string;
  created_at: string;
  updated_at: string;
};
type ActivityLog = {
  id: string;
  project_id: string;
  issue_id: string | null;
  actor_id: string | null;
  action: string;
  details: Record<string, any>;
  created_at: string;
};
type Notification = {
  id: string;
  user_id: string;
  project_id: string | null;
  issue_id: string | null;
  type: string;
  message: string;
  read: boolean;
  created_at: string;
};

// --- STATE MANAGEMENT ---
const state = {
  users: [] as User[],
  projects: [] as Project[],
  board: null as Board | null,
  sprints: [] as Sprint[],
  notifications: [] as Notification[],
  presence: [] as string[], // array of active usernames
  events: [] as string[],   // WebSocket event logs
  
  activeUser: "jane",      // default operator
  activeTab: "board" as "board" | "sprints",
  searchQuery: "",
  filterPriority: "",
  filterType: "",
  filterAssignee: "",
  
  selectedIssue: null as Issue | null,
  selectedIssueComments: [] as Comment[],
  selectedIssueActivities: [] as ActivityLog[],
  drawerStatusSaving: false,
  
  wsConnected: false,
};

let wsConn: WebSocket | null = null;
const apiBase = "";

// --- PREMIUM LIGHT-ACCENTED SVG ICONS ---
function svgEpic() {
  return `<svg class="w-3.5 h-3.5 text-violet-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 12h10L10 22l10-10H10L12 2z"/></svg>`;
}
function svgStory() {
  return `<svg class="w-3.5 h-3.5 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 016.5 2H20v20H6.5a2.5 2.5 0 01-2.5-2.5z"/><path d="M6 6h10M6 10h10"/></svg>`;
}
function svgTask() {
  return `<svg class="w-3.5 h-3.5 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg>`;
}
function svgBug() {
  return `<svg class="w-3.5 h-3.5 text-rose-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="14" x="8" y="5" rx="4"/><path d="M12 2v3M12 19v3M8 8H5M8 12H4M8 16H5M16 8h3M16 12h4M16 16h3"/></svg>`;
}
function svgSubtask() {
  return `<svg class="w-3.5 h-3.5 text-cyan-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v12a2 2 0 002 2h14M9 9l-3 3 3 3M19 12h-9"/></svg>`;
}
function svgBell() {
  return `<svg class="w-4 h-4 text-slate-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0112 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 003.4 0"/></svg>`;
}
function svgWatch(active: boolean) {
  if (active) {
    return `<svg class="w-4 h-4 mr-1 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
  }
  return `<svg class="w-4 h-4 mr-1 opacity-60 text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><path d="M1 1l22 22"/></svg>`;
}
function svgClose() {
  return `<svg class="w-4 h-4 text-slate-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>`;
}
function svgSearch() {
  return `<svg class="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>`;
}
function svgCalendar() {
  return `<svg class="w-3.5 h-3.5 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>`;
}
function svgPulse() {
  return `<svg class="w-4 h-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`;
}
function svgPriority(priority: string) {
  const p = priority.toLowerCase();
  if (p === "high") {
    return `<svg class="w-3 h-3 text-rose-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M18 15l-6-6-6 6"/></svg>`;
  }
  if (p === "medium") {
    return `<svg class="w-3 h-3 text-amber-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/></svg>`;
  }
  return `<svg class="w-3 h-3 text-sky-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>`;
}

// --- UTILITY FUNCTIONS ---
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast(message: string, type: "success" | "error" | "warning" | "info" = "info") {
  const container = document.querySelector("#toast-container");
  if (!container) return;
  const alertColor = 
    type === "success" ? "bg-emerald-50 text-emerald-800 border-emerald-200" : 
    type === "error" ? "bg-rose-50 text-rose-800 border-rose-200" : 
    type === "warning" ? "bg-amber-50 text-amber-800 border-amber-200" : "bg-blue-50 text-blue-800 border-blue-200";
    
  const toast = document.createElement("div");
  toast.className = `alert border p-3.5 shadow-xl rounded-xl flex items-center justify-between gap-4 animate-toast ${alertColor}`;
  toast.innerHTML = `
    <div class="flex items-center gap-2">
      <span class="font-bold text-xs tracking-tight">${escapeHtml(message)}</span>
    </div>
  `;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3800);
}

function userParam(): string {
  return `user_id=${encodeURIComponent(state.activeUser)}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Dev-Token": `dev-${state.activeUser}`,
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw { status: response.status, body };
  }
  return body as T;
}

// High-contrast, highly readable theme tags for light mode
function statusTone(status: string): string {
  if (status === "Done") return "bg-emerald-100 text-emerald-800 border border-emerald-200";
  if (status === "In Review") return "bg-amber-100 text-amber-800 border border-amber-200";
  if (status === "In Progress") return "bg-sky-100 text-sky-800 border border-sky-200";
  if (status === "To Do") return "bg-slate-100 text-slate-800 border border-slate-200";
  return "bg-slate-50 text-slate-500 border border-slate-150";
}

function priorityTone(priority: string): string {
  const p = priority.toLowerCase();
  if (p === "high") return "bg-rose-100 text-rose-800 border border-rose-200";
  if (p === "medium") return "bg-amber-100 text-amber-800 border border-amber-200";
  return "bg-sky-100 text-sky-800 border border-sky-200";
}

function typeIcon(type: string): string {
  switch (type) {
    case "bug": return svgBug();
    case "epic": return svgEpic();
    case "story": return svgStory();
    case "task": return svgTask();
    case "sub_task": return svgSubtask();
    default: return "";
  }
}

function projectId(): string {
  return state.projects[0]?.id || "TS";
}

function logEvent(msg: string) {
  state.events.unshift(`${new Date().toLocaleTimeString()} - ${msg}`);
  state.events = state.events.slice(0, 15);
  updateEventList();
}

// --- DATA FETCHING & SYNC ---
async function loadAllData(silent = false) {
  try {
    if (!silent) {
      const container = document.querySelector("#app");
      if (container && container.innerHTML === "") {
        container.innerHTML = `<div class="flex items-center justify-center min-h-screen bg-[#f2f4f8]"><span class="loading loading-spinner loading-lg text-primary"></span></div>`;
      }
    }
    
    state.users = await request<User[]>("/api/users");
    state.projects = await request<Project[]>("/api/projects");
    if (state.projects.length > 0) {
      const pId = projectId();
      state.board = await request<Board>(`/api/projects/${pId}/board`);
      state.sprints = await request<Sprint[]>(`/api/projects/${pId}/sprints`);
    }
    state.notifications = await request<Notification[]>("/api/notifications");
    
    // Refresh open details state
    if (state.selectedIssue) {
      const freshIssue = state.board?.columns
        .flatMap(c => c.issues)
        .find(i => i.id === state.selectedIssue?.id);
      if (freshIssue) {
        state.selectedIssue = freshIssue;
        state.selectedIssueComments = await request<Comment[]>(`/api/issues/${freshIssue.id}/comments`);
        state.selectedIssueActivities = await request<ActivityLog[]>(`/api/projects/${projectId()}/activity?issue_id=${freshIssue.id}`);
      }
    }
  } catch (err: any) {
    console.error(err);
    showToast("Error loading project space", "error");
  }
}

// --- WEBSOCKET REAL-TIME SYNC ---
function connectWebSocket() {
  if (wsConn) {
    wsConn.close();
  }
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const pId = projectId();
  wsConn = new WebSocket(`${protocol}://${location.host}/ws/projects/${pId}?last_event_id=0&user_id=${state.activeUser}`);
  
  wsConn.onopen = () => {
    state.wsConnected = true;
    logEvent("Real-time telemetry synced");
    updateNavbarPresence();
  };
  
  wsConn.onmessage = async (evt) => {
    try {
      const data = JSON.parse(evt.data);
      if (data.type === "presence") {
        state.presence = data.users || [];
        updateNavbarPresence();
      } else {
        logEvent(`Signal: ${data.type || "Event"} triggered`);
        await loadAllData(true);
        renderWorkspace();
        if (state.selectedIssue) {
          updateDetailDrawer();
        }
      }
    } catch (err) {
      console.error("WS parse error", err);
    }
  };
  
  wsConn.onerror = () => {
    logEvent("Real-time telemetry disconnected");
  };
  
  wsConn.onclose = () => {
    state.wsConnected = false;
    updateNavbarPresence();
    setTimeout(connectWebSocket, 4000);
  };
}

// --- DRAG AND DROP KANBAN ---
function setupDragAndDrop() {
  const cards = document.querySelectorAll(".issue-card");
  cards.forEach(card => {
    card.addEventListener("dragstart", (e: any) => {
      e.dataTransfer.setData("text/plain", card.getAttribute("data-id"));
      e.dataTransfer.effectAllowed = "move";
      card.classList.add("opacity-45");
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("opacity-45");
    });
  });

  const columns = document.querySelectorAll(".board-column");
  columns.forEach(col => {
    col.addEventListener("dragover", (e: any) => {
      e.preventDefault();
      col.classList.add("drag-over");
    });
    col.addEventListener("dragleave", () => {
      col.classList.remove("drag-over");
    });
    col.addEventListener("drop", async (e: any) => {
      e.preventDefault();
      col.classList.remove("drag-over");
      const issueId = e.dataTransfer.getData("text/plain");
      const targetStatus = col.getAttribute("data-status");
      if (!issueId || !targetStatus) return;
      
      const issue = state.board?.columns.flatMap(c => c.issues).find(i => i.id === issueId);
      if (!issue || issue.status === targetStatus) return;
      
      try {
        await request(`/api/issues/${issueId}/transitions?${userParam()}`, {
          method: "POST",
          body: JSON.stringify({ to_status: targetStatus, expected_version: issue.version }),
        });
        showToast(`Moved ${issue.issue_key} to ${targetStatus}`, "success");
        await loadAllData(true);
        renderWorkspace();
      } catch (err: any) {
        console.error(err);
        const allowed = err.body?.detail?.allowed_transitions?.join(", ") || "None";
        showToast(`Workflow Violation: Cannot move issue. Allowed: [${allowed}]`, "error");
      }
    });
  });
}

// --- DOM RENDER CHUNKS ---
function renderNavbar() {
  const totalUnread = state.notifications.filter(n => !n.read).length;
  const navbar = document.querySelector("#navbar-container");
  if (!navbar) return;
  
  navbar.innerHTML = `
    <div class="navbar rounded-2xl glass-panel px-6 py-4 shadow-xl flex flex-col lg:flex-row gap-4 items-center justify-between">
      <div class="flex items-center gap-6">
        <div>
          <p class="text-[10px] font-bold uppercase tracking-[0.35em] text-primary font-mono-tag">TeamSync Space</p>
          <h1 class="text-xl font-bold tracking-tight text-slate-800 leading-tight">Mission Control</h1>
        </div>
        
        <div class="tabs tabs-boxed bg-slate-200 border border-slate-300/40 p-1 flex gap-1 rounded-xl">
          <button id="tab-board" class="btn btn-ghost btn-xs text-xs font-semibold rounded-lg px-3 py-1 ${state.activeTab === "board" ? "bg-primary text-white shadow" : "text-slate-700"}">Kanban Board</button>
          <button id="tab-sprints" class="btn btn-ghost btn-xs text-xs font-semibold rounded-lg px-3 py-1 ${state.activeTab === "sprints" ? "bg-primary text-white shadow" : "text-slate-700"}">Sprint Backlog</button>
        </div>
      </div>

      <!-- Online Presence List -->
      <div class="flex flex-wrap items-center gap-4">
        <div id="presence-list" class="flex -space-x-1.5 items-center">
          <!-- Populated by updateNavbarPresence -->
        </div>
        
        <!-- Notifications Bell -->
        <div class="dropdown dropdown-end">
          <div tabindex="0" role="button" class="btn btn-ghost btn-circle relative bg-slate-200/50 border border-slate-350">
            ${svgBell()}
            ${totalUnread > 0 ? `<span class="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-primary animate-pulse"></span>` : ""}
          </div>
          <ul tabindex="0" class="dropdown-content menu p-3 shadow-2xl bg-white border border-slate-200 rounded-2xl w-80 max-h-96 overflow-y-auto mt-2 z-50">
            <h3 class="font-bold text-xs uppercase tracking-wider text-slate-500 mb-2 px-2 border-b border-slate-100 pb-2">Recent Notifications</h3>
            ${state.notifications.length === 0 
              ? `<div class="text-[11px] text-slate-400 text-center py-4">No notifications</div>`
              : state.notifications.map(n => `
                  <li class="border-b border-slate-100 last:border-b-0 py-2.5 px-2 hover:bg-slate-50 rounded-lg transition duration-200">
                    <p class="text-xs font-semibold leading-normal text-slate-800">${escapeHtml(n.message)}</p>
                    <span class="text-[9px] text-slate-400 block mt-1 font-mono">${new Date(n.created_at).toLocaleTimeString()}</span>
                  </li>
                `).join("")}
          </ul>
        </div>

        <select id="active-user-select" class="select select-sm select-bordered w-36 font-semibold rounded-lg">
          ${state.users.map(u => `<option value="${u.username}" ${u.username === state.activeUser ? "selected" : ""}>${escapeHtml(u.display_name)}</option>`).join("")}
        </select>
        
        <button id="btn-create-issue" class="btn btn-primary btn-sm font-bold shadow-lg shadow-primary/10 rounded-lg">
          <span>+ Create Issue</span>
        </button>
      </div>
    </div>
  `;

  // Attach navbar listener triggers
  document.querySelector("#tab-board")?.addEventListener("click", () => {
    state.activeTab = "board";
    renderWorkspace();
    renderNavbar();
  });
  document.querySelector("#tab-sprints")?.addEventListener("click", () => {
    state.activeTab = "sprints";
    renderWorkspace();
    renderNavbar();
  });
  document.querySelector("#active-user-select")?.addEventListener("change", async (e: any) => {
    state.activeUser = e.target.value;
    logEvent(`Switched actor to: ${state.activeUser}`);
    await loadAllData(true);
    connectWebSocket(); 
    renderWorkspace();
    renderNavbar();
  });
  document.querySelector("#btn-create-issue")?.addEventListener("click", () => {
    const modal = document.querySelector<HTMLDialogElement>("#create-issue-modal");
    if (modal) {
      renderCreateIssueModalContent();
      modal.showModal();
    }
  });

  updateNavbarPresence();
}

function updateNavbarPresence() {
  const presenceContainer = document.querySelector("#presence-list");
  if (!presenceContainer) return;
  
  if (state.presence.length === 0) {
    presenceContainer.innerHTML = `<span class="text-[10px] text-slate-400 uppercase tracking-widest font-mono-tag">Offline</span>`;
    return;
  }
  
  presenceContainer.innerHTML = state.presence.map(username => {
    const user = state.users.find(u => u.username === username);
    const initials = user ? user.display_name.split(" ").map(n=>n[0]).join("") : username.substring(0, 2);
    return `
      <div class="avatar placeholder" title="${escapeHtml(user?.display_name || username)} (Online)">
        <div class="bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-full w-7 h-7 text-[9px] font-extrabold shadow-sm">
          <span>${initials.toUpperCase()}</span>
        </div>
      </div>
    `;
  }).join("");
}

function updateEventList() {
  const list = document.querySelector("#ws-events-list");
  if (!list) return;
  list.innerHTML = state.events.map(ev => `
    <div class="py-1.5 border-b border-slate-200/60 last:border-0 text-[10px] font-mono text-slate-500">
      ${escapeHtml(ev)}
    </div>
  `).join("") || `<div class="text-[10px] text-slate-400 font-mono">Waiting for updates...</div>`;
}

function renderWorkspace() {
  const container = document.querySelector("#workspace-container");
  if (!container) return;

  if (state.activeTab === "board") {
    const columns = state.board?.columns ?? [];
    
    // Apply local filters
    const filteredColumns = columns.map(col => {
      const filteredIssues = col.issues.filter(issue => {
        const matchesSearch = state.searchQuery === "" 
          || issue.title.toLowerCase().includes(state.searchQuery.toLowerCase())
          || issue.issue_key.toLowerCase().includes(state.searchQuery.toLowerCase())
          || (issue.description && issue.description.toLowerCase().includes(state.searchQuery.toLowerCase()));
        
        const matchesPriority = state.filterPriority === "" || issue.priority.toLowerCase() === state.filterPriority.toLowerCase();
        const matchesType = state.filterType === "" || issue.type === state.filterType;
        const matchesAssignee = state.filterAssignee === "" || (issue.assignee && issue.assignee.id === state.filterAssignee);
        
        return matchesSearch && matchesPriority && matchesType && matchesAssignee;
      });
      return { ...col, issues: filteredIssues };
    });

    container.innerHTML = `
      <div class="space-y-6">
        <!-- Filter Controls -->
        <div class="flex flex-wrap items-center justify-between gap-4 glass-panel p-4 rounded-xl shadow border border-slate-200">
          <div class="flex flex-wrap items-center gap-3 flex-1">
            <div class="relative w-full max-w-xs">
              <span class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                ${svgSearch()}
              </span>
              <input id="board-search" type="text" placeholder="Filter by key or summary..." value="${escapeHtml(state.searchQuery)}" class="input input-sm pl-9 w-full rounded-lg font-medium text-xs bg-white" />
            </div>
            
            <select id="filter-type" class="select select-sm font-medium rounded-lg text-xs">
              <option value="">All Types</option>
              <option value="epic" ${state.filterType === "epic" ? "selected" : ""}>💎 Epic</option>
              <option value="story" ${state.filterType === "story" ? "selected" : ""}>📖 Story</option>
              <option value="task" ${state.filterType === "task" ? "selected" : ""}>✅ Task</option>
              <option value="bug" ${state.filterType === "bug" ? "selected" : ""}>🐛 Bug</option>
              <option value="sub_task" ${state.filterType === "sub_task" ? "selected" : ""}>🌿 Sub-task</option>
            </select>
            
            <select id="filter-priority" class="select select-sm font-medium rounded-lg text-xs">
              <option value="">All Priorities</option>
              <option value="high" ${state.filterPriority === "high" ? "selected" : ""}>🔴 High</option>
              <option value="medium" ${state.filterPriority === "medium" ? "selected" : ""}>🟡 Medium</option>
              <option value="low" ${state.filterPriority === "low" ? "selected" : ""}>🔵 Low</option>
            </select>
            
            <select id="filter-assignee" class="select select-sm font-medium rounded-lg text-xs">
              <option value="">All Assignees</option>
              ${state.users.map(u => `<option value="${u.id}" ${state.filterAssignee === u.id ? "selected" : ""}>${escapeHtml(u.display_name)}</option>`).join("")}
            </select>
          </div>
          
          <button id="btn-clear-filters" class="btn btn-sm btn-ghost font-semibold text-xs rounded-lg">Clear Filters</button>
        </div>

        <!-- Columns Grid (Bento Panels layout) -->
        <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 items-start">
          ${filteredColumns.map(col => `
            <div class="board-column rounded-2xl p-4 flex flex-col max-h-[75vh]" data-status="${escapeHtml(col.status.name)}">
              <div class="mb-4 flex items-center justify-between border-b border-slate-300/60 pb-2">
                <span class="font-extrabold text-[11px] tracking-wider uppercase text-slate-600">${escapeHtml(col.status.name)}</span>
                <span class="badge ${statusTone(col.status.name)} px-2 py-0.5 text-[9px] rounded-md">${col.issues.length}</span>
              </div>
              
              <div class="space-y-3 overflow-y-auto custom-scrollbar flex-1 pb-4">
                ${col.issues.map(issue => {
                  const initial = issue.assignee ? issue.assignee.display_name.split(" ").map(n=>n[0]).join("") : "U";
                  return `
                    <div class="issue-card rounded-xl p-3 shadow-sm cursor-pointer" data-id="${issue.id}" draggable="true">
                      <div class="flex items-center justify-between gap-2">
                        <span class="text-[9px] font-bold text-slate-500 flex items-center gap-1.5 font-mono-tag">
                          <span>${typeIcon(issue.type)}</span>
                          <span>${issue.issue_key}</span>
                        </span>
                        <span class="badge ${priorityTone(issue.priority)} px-1.5 py-0.5 text-[8px] rounded">${issue.priority.toUpperCase()}</span>
                      </div>
                      
                      <h3 class="mt-2 text-xs font-bold leading-normal tracking-tight text-slate-800 line-clamp-2">${escapeHtml(issue.title)}</h3>
                      
                      <div class="mt-4 flex items-center justify-between border-t border-slate-100 pt-2">
                        <div class="flex items-center gap-1.5">
                          ${issue.story_points !== null ? `<span class="badge bg-slate-100 text-slate-700 px-1.5 py-0.5 text-[9px] rounded font-bold">${issue.story_points} SP</span>` : ""}
                          <span class="text-[8px] opacity-50 font-mono font-bold">V${issue.version}</span>
                        </div>
                        <div class="avatar placeholder">
                          <div class="bg-slate-100 text-slate-700 border border-slate-200 rounded-full w-5.5 h-5.5 text-[8px] font-extrabold" title="${issue.assignee ? escapeHtml(issue.assignee.display_name) : 'Unassigned'}">
                            <span>${initial.toUpperCase()}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  `;
                }).join("")}
                ${col.issues.length === 0 ? `<div class="text-[10px] text-slate-400 text-center py-8 font-medium">Drop tasks here</div>` : ""}
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `;

    // Filter listeners
    document.querySelector("#board-search")?.addEventListener("input", (e: any) => {
      state.searchQuery = e.target.value;
      renderWorkspace();
    });
    document.querySelector("#filter-type")?.addEventListener("change", (e: any) => {
      state.filterType = e.target.value;
      renderWorkspace();
    });
    document.querySelector("#filter-priority")?.addEventListener("change", (e: any) => {
      state.filterPriority = e.target.value;
      renderWorkspace();
    });
    document.querySelector("#filter-assignee")?.addEventListener("change", (e: any) => {
      state.filterAssignee = e.target.value;
      renderWorkspace();
    });
    document.querySelector("#btn-clear-filters")?.addEventListener("click", () => {
      state.searchQuery = "";
      state.filterPriority = "";
      state.filterType = "";
      state.filterAssignee = "";
      renderWorkspace();
    });

    // Card click details trigger
    document.querySelectorAll(".issue-card").forEach(card => {
      card.addEventListener("click", async () => {
        const id = card.getAttribute("data-id");
        if (id) {
          await openDetailDrawer(id);
        }
      });
    });

    setupDragAndDrop();
  } else {
    // Sprints Backlog rendering
    const activeSprint = state.sprints.find(s => s.status === "active");
    const plannedSprints = state.sprints.filter(s => s.status === "planned");
    const completedSprints = state.sprints.filter(s => s.status === "completed");
    
    // Find backlog issues (those with no sprint assigned)
    const allIssues = state.board?.columns.flatMap(c => c.issues) ?? [];
    const backlogIssues = allIssues.filter(i => !i.sprint);

    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex items-center justify-between glass-panel p-4 rounded-xl border border-slate-200">
          <div>
            <h2 class="text-sm font-extrabold uppercase tracking-wider text-slate-800">Sprint Cycles</h2>
            <p class="text-[10px] text-slate-400 font-mono-tag">Organize cycles, allocate resources, and measure velocity</p>
          </div>
          <button id="btn-create-sprint" class="btn btn-sm btn-outline btn-primary font-bold rounded-lg text-xs">Create Sprint</button>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-[1.4fr_0.8fr] gap-6 items-start">
          <div class="space-y-6">
            <!-- Active Sprint section -->
            <div class="collapse collapse-arrow bg-white border border-slate-200 rounded-2xl shadow-sm">
              <input type="checkbox" checked /> 
              <div class="collapse-title flex items-center justify-between pr-12">
                <div class="flex items-center gap-3">
                  <span class="badge bg-emerald-100 text-emerald-800 border border-emerald-200 font-bold text-[9px] rounded">ACTIVE</span>
                  <span class="font-extrabold text-xs tracking-wider uppercase text-slate-700">${activeSprint ? escapeHtml(activeSprint.name) : "No Active Sprints"}</span>
                </div>
                ${activeSprint ? `<button id="btn-complete-sprint" class="btn btn-xs btn-error font-bold rounded text-[10px]" data-id="${activeSprint.id}">Complete Sprint</button>` : ""}
              </div>
              <div class="collapse-content space-y-4 pt-2">
                ${activeSprint 
                  ? renderSprintIssueList(allIssues.filter(i => i.sprint?.id === activeSprint.id))
                  : `<p class="text-xs text-slate-400 py-2 font-medium">Activate a planned cycle below to start tracking.</p>`
                }
              </div>
            </div>

            <!-- Planned Sprints -->
            <div class="space-y-4">
              <h3 class="text-[10px] font-extrabold uppercase tracking-widest text-slate-450 font-mono-tag">Planned Sprints</h3>
              ${plannedSprints.length === 0 
                ? `<div class="bg-white border border-dashed border-slate-200 rounded-2xl py-8 text-center text-xs text-slate-400 font-medium shadow-sm">No planned cycles mapped.</div>`
                : plannedSprints.map(s => `
                    <div class="collapse collapse-arrow bg-white border border-slate-200 rounded-2xl shadow-sm">
                      <input type="checkbox" /> 
                      <div class="collapse-title flex items-center justify-between pr-12">
                        <div class="flex items-center gap-3">
                          <span class="badge bg-slate-100 text-slate-600 font-bold text-[9px] rounded">PLANNED</span>
                          <span class="font-bold text-xs tracking-wide text-slate-700">${escapeHtml(s.name)}</span>
                        </div>
                        <button class="btn-start-sprint btn btn-xs btn-success font-bold rounded text-[10px]" data-id="${s.id}">Start Sprint</button>
                      </div>
                      <div class="collapse-content space-y-4 pt-2">
                        ${renderSprintIssueList(allIssues.filter(i => i.sprint?.id === s.id))}
                      </div>
                    </div>
                  `).join("")}
            </div>

            <!-- Backlog Issues -->
            <div class="collapse collapse-arrow bg-white border border-slate-200 rounded-2xl shadow-sm">
              <input type="checkbox" checked /> 
              <div class="collapse-title flex items-center gap-3">
                <span class="badge bg-slate-100 text-slate-600 font-bold text-[9px] rounded">${backlogIssues.length}</span>
                <span class="font-extrabold text-xs tracking-wider uppercase text-slate-700">Global Backlog</span>
              </div>
              <div class="collapse-content space-y-4 pt-2">
                ${renderSprintIssueList(backlogIssues)}
              </div>
            </div>
          </div>

          <!-- Completed Sprints Statistics -->
          <div class="glass-panel p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
            <h3 class="text-[10px] font-extrabold uppercase tracking-widest text-slate-450 font-mono-tag">Completed History</h3>
            <div class="space-y-3 overflow-y-auto max-h-[55vh] custom-scrollbar">
              ${completedSprints.length === 0
                ? `<div class="text-[10px] text-slate-400 font-medium py-6 text-center">No completed cycles recorded.</div>`
                : completedSprints.map(s => `
                    <div class="p-3 border-b border-slate-100 last:border-0 flex items-center justify-between gap-4">
                      <div>
                        <h4 class="text-xs font-bold text-slate-800">${escapeHtml(s.name)}</h4>
                        <span class="text-[9px] opacity-50 font-mono">Completed: ${s.completed_at ? new Date(s.completed_at).toLocaleDateString() : ""}</span>
                      </div>
                      <span class="badge bg-slate-100 text-slate-500 text-[8px] font-extrabold rounded">COMPLETED</span>
                    </div>
                  `).join("")}
            </div>
          </div>
        </div>
      </div>
    `;

    // Sprint actions listeners
    document.querySelector("#btn-create-sprint")?.addEventListener("click", () => {
      const modal = document.querySelector<HTMLDialogElement>("#create-sprint-modal");
      if (modal) {
        modal.showModal();
      }
    });

    document.querySelectorAll(".btn-start-sprint").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const sprintId = btn.getAttribute("data-id");
        if (!sprintId) return;
        try {
          await request(`/api/sprints/${sprintId}/start?${userParam()}`, { method: "POST" });
          showToast("Sprint successfully started", "success");
          await loadAllData(true);
          renderWorkspace();
        } catch (err: any) {
          showToast(`Failed to start sprint: ${err.body?.detail?.message || err.status}`, "error");
        }
      });
    });

    document.querySelector("#btn-complete-sprint")?.addEventListener("click", async (e: any) => {
      e.stopPropagation();
      const sId = e.target.getAttribute("data-id");
      if (!sId) return;
      openCompleteSprintModal(sId);
    });

    // Handle clicking issue cards inside sprint view lists
    document.querySelectorAll(".sprint-issue-item").forEach(item => {
      item.addEventListener("click", async () => {
        const id = item.getAttribute("data-id");
        if (id) {
          await openDetailDrawer(id);
        }
      });
    });
  }
}

function renderSprintIssueList(issues: Issue[]): string {
  if (issues.length === 0) {
    return `<div class="text-[10px] text-slate-400 py-3 text-center font-medium">No tasks assigned.</div>`;
  }
  return `
    <div class="overflow-x-auto w-full">
      <table class="table table-xs w-full text-slate-800">
        <thead>
          <tr class="border-b border-slate-100">
            <th class="text-[9px] uppercase tracking-wider text-slate-450 font-mono-tag">Key</th>
            <th class="text-[9px] uppercase tracking-wider text-slate-450 font-mono-tag">Type</th>
            <th class="text-[9px] uppercase tracking-wider text-slate-450 font-mono-tag">Summary</th>
            <th class="text-[9px] uppercase tracking-wider text-slate-450 font-mono-tag">Status</th>
            <th class="text-[9px] uppercase tracking-wider text-slate-450 font-mono-tag">Priority</th>
            <th class="text-[9px] uppercase tracking-wider text-slate-450 font-mono-tag">SP</th>
            <th class="text-[9px] uppercase tracking-wider text-slate-450 font-mono-tag">Assignee</th>
          </tr>
        </thead>
        <tbody>
          ${issues.map(issue => `
            <tr class="sprint-issue-item hover cursor-pointer border-b border-slate-100 hover:bg-slate-50 transition" data-id="${issue.id}">
              <td class="font-bold text-[10px] font-mono-tag text-slate-600">${issue.issue_key}</td>
              <td class="align-middle">${typeIcon(issue.type)}</td>
              <td class="max-w-[200px] truncate text-xs font-semibold text-slate-800">${escapeHtml(issue.title)}</td>
              <td><span class="badge ${statusTone(issue.status)} font-bold text-[9px] px-1.5 py-0.5 rounded">${issue.status}</span></td>
              <td><span class="badge ${priorityTone(issue.priority)} font-bold text-[9px] px-1.5 py-0.5 rounded">${issue.priority.toUpperCase()}</span></td>
              <td><span class="font-mono text-xs text-slate-700 font-bold">${issue.story_points ?? 0}</span></td>
              <td class="text-xs text-slate-700">${issue.assignee ? escapeHtml(issue.assignee.display_name) : "Unassigned"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

// --- ISSUE DETAIL DRAWER ---
async function openDetailDrawer(issueId: string) {
  try {
    const issue = state.board?.columns.flatMap(c => c.issues).find(i => i.id === issueId);
    if (!issue) return;
    state.selectedIssue = issue;
    state.drawerStatusSaving = false;
    
    state.selectedIssueComments = await request<Comment[]>(`/api/issues/${issueId}/comments`);
    state.selectedIssueActivities = await request<ActivityLog[]>(`/api/projects/${projectId()}/activity?issue_id=${issueId}`);
    
    const drawer = document.querySelector("#detail-drawer");
    if (drawer) {
      drawer.classList.remove("translate-x-full");
      updateDetailDrawer();
    }
  } catch (err) {
    console.error(err);
    showToast("Error loading issue details", "error");
  }
}

function closeDetailDrawer() {
  const drawer = document.querySelector("#detail-drawer");
  if (drawer) {
    drawer.classList.add("translate-x-full");
    state.selectedIssue = null;
  }
}

function updateDetailDrawer() {
  const issue = state.selectedIssue;
  const drawerContent = document.querySelector("#detail-drawer-content");
  if (!issue || !drawerContent) return;

  const totalPoints = issue.story_points ?? 0;
  const isWatching = issue.watchers.includes(state.activeUser);
  
  const allIssues = state.board?.columns.flatMap(c => c.issues) ?? [];
  const parentCandidates = allIssues.filter(i => i.id !== issue.id && i.type !== "sub_task");
  
  drawerContent.innerHTML = `
    <div class="h-full flex flex-col justify-between">
      <!-- Scrollable Panel Body -->
      <div class="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-6">
        <!-- Header key and close button -->
        <div class="flex items-center justify-between border-b border-slate-200 pb-4">
          <div class="flex items-center gap-3">
            <span class="text-xs font-bold bg-slate-100 border border-slate-200 px-2.5 py-1 rounded-lg text-slate-800 flex items-center gap-1.5 font-mono-tag">
              <span>${typeIcon(issue.type)}</span>
              <span>${issue.issue_key}</span>
            </span>
            <span class="text-[9px] opacity-50 font-mono font-bold uppercase tracking-wider text-slate-500">Version: ${issue.version}</span>
          </div>
          <button id="btn-close-drawer" class="btn btn-sm btn-ghost btn-circle bg-slate-100 border border-slate-200">
            ${svgClose()}
          </button>
        </div>

        <!-- Layout split: Left metadata detail / Right comment thread -->
        <div class="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-6 items-start">
          
          <!-- Column 1: Core issue properties -->
          <div class="space-y-5 bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
            <div>
              <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Summary</label>
              <input id="drawer-title" type="text" value="${escapeHtml(issue.title)}" class="input input-sm w-full font-bold text-sm bg-slate-50 rounded-lg text-slate-800" />
            </div>

            <div>
              <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Description</label>
              <textarea id="drawer-desc" rows="5" placeholder="Add descriptive details..." class="textarea textarea-sm w-full font-medium text-xs bg-slate-50 rounded-lg text-slate-850 leading-relaxed">${escapeHtml(issue.description || "")}</textarea>
            </div>
            
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Status</label>
                <select id="drawer-status" class="select select-sm w-full font-semibold bg-slate-50 rounded-lg text-xs" ${state.drawerStatusSaving ? "disabled" : ""}>
                  ${state.board?.columns.map(col => `<option value="${col.status.name}" ${col.status.name === issue.status ? "selected" : ""}>${escapeHtml(col.status.name)}</option>`).join("")}
                </select>
              </div>
              
              <div>
                <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Priority</label>
                <select id="drawer-priority" class="select select-sm w-full font-semibold bg-slate-50 rounded-lg text-xs">
                  <option value="high" ${issue.priority.toLowerCase() === "high" ? "selected" : ""}>🔴 High</option>
                  <option value="medium" ${issue.priority.toLowerCase() === "medium" ? "selected" : ""}>🟡 Medium</option>
                  <option value="low" ${issue.priority.toLowerCase() === "low" ? "selected" : ""}>🔵 Low</option>
                </select>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Assignee</label>
                <select id="drawer-assignee" class="select select-sm w-full font-semibold bg-slate-50 rounded-lg text-xs">
                  <option value="">Unassigned</option>
                  ${state.users.map(u => `<option value="${u.id}" ${issue.assignee?.id === u.id ? "selected" : ""}>${escapeHtml(u.display_name)}</option>`).join("")}
                </select>
              </div>
              
              <div>
                <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Story Points</label>
                <input id="drawer-points" type="number" min="0" value="${totalPoints}" class="input input-sm w-full font-semibold bg-slate-50 rounded-lg text-xs" />
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Sprint Cycle</label>
                <select id="drawer-sprint" class="select select-sm w-full font-semibold bg-slate-50 rounded-lg text-xs">
                  <option value="">Backlog (No Sprint)</option>
                  ${state.sprints.map(s => `<option value="${s.id}" ${issue.sprint?.id === s.id ? "selected" : ""}>${escapeHtml(s.name)} (${s.status})</option>`).join("")}
                </select>
              </div>

              <div>
                <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Parent link</label>
                <select id="drawer-parent" class="select select-sm w-full font-semibold bg-slate-50 rounded-lg text-xs">
                  <option value="">No Parent</option>
                  ${parentCandidates.map(p => `<option value="${p.id}" ${issue.parent_id === p.id ? "selected" : ""}>${p.issue_key} - ${escapeHtml(p.title)}</option>`).join("")}
                </select>
              </div>
            </div>

            <div class="flex items-center justify-between border-t border-slate-100 pt-4">
              <button id="btn-save-issue" class="btn btn-sm btn-primary font-bold rounded-lg text-xs text-white" ${state.drawerStatusSaving ? "disabled" : ""}>Save Changes</button>
              
              <button id="btn-toggle-watch" class="btn btn-sm ${isWatching ? 'btn-neutral' : 'btn-outline btn-primary'} font-bold rounded-lg text-xs">
                ${svgWatch(isWatching)} ${isWatching ? "Unwatch" : "Watch"}
              </button>
            </div>
            
            <!-- Watchers list display -->
            <div class="mt-4 pt-3 border-t border-slate-100">
              <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-2 font-mono-tag text-slate-500">Watchers (${issue.watchers.length})</label>
              <div class="flex flex-wrap gap-1.5">
                ${issue.watchers.map(username => {
                  const user = state.users.find(u => u.username === username);
                  return `<span class="badge bg-slate-100 text-slate-700 text-[9px] font-bold px-2 py-0.5 rounded border border-slate-200/60">${escapeHtml(user?.display_name || username)}</span>`;
                }).join("")}
                ${issue.watchers.length === 0 ? `<span class="text-xs text-slate-400 font-medium">No watchers</span>` : ""}
              </div>
            </div>
          </div>

          <!-- Column 2: Comments & Specific Audit Activities -->
          <div class="space-y-6">
            <!-- Comment Section -->
            <div class="glass-panel p-4 rounded-2xl border border-slate-200 space-y-4 shadow-sm bg-white">
              <h4 class="text-[9px] font-extrabold uppercase tracking-widest text-slate-500 font-mono-tag">Comments Thread</h4>
              
              <div class="space-y-3 max-h-64 overflow-y-auto custom-scrollbar pr-1">
                ${state.selectedIssueComments.length === 0
                  ? `<p class="text-[10px] text-slate-400 text-center py-4 font-medium">No comments yet. Support @mentions.</p>`
                  : renderCommentTree(state.selectedIssueComments)
                }
              </div>
              
              <div class="flex gap-2">
                <input id="new-comment-body" type="text" placeholder="Add comment... Use @jane/bob/maya" class="input input-sm rounded-lg flex-1 text-xs" />
                <button id="btn-add-comment" class="btn btn-sm btn-primary font-bold rounded-lg text-xs text-white">Send</button>
              </div>
            </div>

            <!-- Audit Trail Log for this specific issue -->
            <div class="glass-panel p-4 rounded-2xl border border-slate-200 space-y-3 max-h-60 overflow-y-auto custom-scrollbar shadow-sm bg-white">
              <h4 class="text-[9px] font-extrabold uppercase tracking-widest text-slate-500 font-mono-tag flex items-center gap-1.5">
                ${svgPulse()} Audit Timeline
              </h4>
              <div class="space-y-2.5">
                ${state.selectedIssueActivities.map(act => `
                  <div class="text-[10px] leading-relaxed border-b border-slate-100 pb-2 last:border-0 text-slate-600">
                    <span class="font-bold text-slate-700 uppercase tracking-tight text-[9px] bg-slate-100 border border-slate-200 px-1 py-0.5 rounded">${escapeHtml(act.action.replace("_", " "))}</span> by 
                    <span class="font-bold text-primary">${escapeHtml(state.users.find(u => u.id === act.actor_id)?.username || "system")}</span>
                    <span class="text-[8px] opacity-50 block mt-0.5 font-mono font-bold">${new Date(act.created_at).toLocaleString()}</span>
                  </div>
                `).join("")}
                ${state.selectedIssueActivities.length === 0 ? `<p class="text-[10px] text-slate-400 text-center py-2 font-medium">No activity recorded</p>` : ""}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  const statusSelect = document.querySelector("#drawer-status") as HTMLSelectElement | null;
  statusSelect?.addEventListener("change", async () => {
    const current = state.selectedIssue;
    if (!current || state.drawerStatusSaving) return;
    const nextStatus = statusSelect.value;
    if (nextStatus === current.status) return;

    const previousStatus = current.status;
    state.drawerStatusSaving = true;
    current.status = nextStatus;
    updateDetailDrawer();

    try {
      await request(`/api/issues/${current.id}/transitions?${userParam()}`, {
        method: "POST",
        body: JSON.stringify({ to_status: nextStatus, expected_version: current.version }),
      });
      showToast(`Status moved to ${nextStatus}`, "success");
      await loadAllData(true);
      renderWorkspace();
      const fresh = state.board?.columns.flatMap(c => c.issues).find(i => i.id === current.id);
      if (fresh) {
        state.selectedIssue = fresh;
      }
      state.drawerStatusSaving = false;
      updateDetailDrawer();
    } catch (err: any) {
      current.status = previousStatus;
      state.drawerStatusSaving = false;
      console.error(err);
      if (statusSelect) statusSelect.value = previousStatus;
      if (err.status === 409) {
        showToast("Conflict: This issue changed elsewhere. Reloading data...", "warning");
      } else {
        showToast(`Failed to update status: ${err.body?.detail?.message || err.status}`, "error");
      }
      await loadAllData(true);
      renderWorkspace();
      const fresh = state.board?.columns.flatMap(c => c.issues).find(i => i.id === current.id);
      if (fresh) {
        state.selectedIssue = fresh;
      }
      updateDetailDrawer();
    }
  });

  // Attach Details actions
  document.querySelector("#btn-close-drawer")?.addEventListener("click", closeDetailDrawer);
  
  document.querySelector("#btn-save-issue")?.addEventListener("click", async () => {
    if (state.drawerStatusSaving) return;
    const title = (document.querySelector("#drawer-title") as HTMLInputElement).value;
    const desc = (document.querySelector("#drawer-desc") as HTMLTextAreaElement).value;
    const priority = (document.querySelector("#drawer-priority") as HTMLSelectElement).value;
    const assigneeId = (document.querySelector("#drawer-assignee") as HTMLSelectElement).value || null;
    const pointsText = (document.querySelector("#drawer-points") as HTMLInputElement).value;
    const sprintId = (document.querySelector("#drawer-sprint") as HTMLSelectElement).value || null;
    const parentId = (document.querySelector("#drawer-parent") as HTMLSelectElement).value || null;
    
    const points = pointsText !== "" ? parseInt(pointsText, 10) : null;
    
    try {
      await request(`/api/issues/${issue.id}?${userParam()}`, {
        method: "PATCH",
        body: JSON.stringify({
          title,
          description: desc,
          priority,
          assignee_id: assigneeId,
          sprint_id: sprintId,
          story_points: points,
          parent_id: parentId,
          expected_version: issue.version,
        }),
      });

      showToast("Issue successfully updated", "success");
      await loadAllData(true);
      renderWorkspace();
      const fresh = state.board?.columns.flatMap(c => c.issues).find(i => i.id === issue.id);
      if (fresh) {
        state.selectedIssue = fresh;
        updateDetailDrawer();
      }
    } catch (err: any) {
      console.error(err);
      if (err.status === 409) {
        showToast("Conflict: This issue was modified elsewhere. Reloading data...", "warning");
      } else {
        showToast(`Failed to update issue: ${err.body?.detail?.message || err.status}`, "error");
      }
      await loadAllData(true);
      renderWorkspace();
    }
  });

  document.querySelector("#btn-toggle-watch")?.addEventListener("click", async () => {
    try {
      const url = `/api/issues/${issue.id}/watch?${userParam()}`;
      if (isWatching) {
        await request(url, { method: "DELETE" });
        showToast("Stopped watching issue", "info");
      } else {
        await request(url, { method: "POST" });
        showToast("Started watching issue", "success");
      }
      await loadAllData(true);
      updateDetailDrawer();
    } catch (err: any) {
      showToast("Error updating watch status", "error");
    }
  });

  document.querySelector("#btn-add-comment")?.addEventListener("click", async () => {
    const input = document.querySelector("#new-comment-body") as HTMLInputElement;
    const body = input.value.trim();
    if (!body) return;
    try {
      await request(`/api/issues/${issue.id}/comments?${userParam()}`, {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      input.value = "";
      showToast("Comment added", "success");
      await loadAllData(true);
      state.selectedIssueComments = await request<Comment[]>(`/api/issues/${issue.id}/comments`);
      updateDetailDrawer();
    } catch (err: any) {
      showToast("Failed to post comment", "error");
    }
  });

  document.querySelectorAll(".btn-delete-comment").forEach(btn => {
    btn.addEventListener("click", async () => {
      const cId = btn.getAttribute("data-id");
      if (!cId) return;
      try {
        await request(`/api/comments/${cId}?${userParam()}`, { method: "DELETE" });
        showToast("Comment deleted", "info");
        await loadAllData(true);
        state.selectedIssueComments = await request<Comment[]>(`/api/issues/${issue.id}/comments`);
        updateDetailDrawer();
      } catch (err) {
        showToast("Failed to delete comment", "error");
      }
    });
  });
}

function renderCommentTree(comments: Comment[]): string {
  const sorted = [...comments].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  
  return sorted.map(c => {
    const initial = c.author.display_name.split(" ").map(n => n[0]).join("");
    const isOwner = c.author.username === state.activeUser;
    
    return `
      <div class="bg-slate-50 p-2.5 rounded-xl border border-slate-200/60 space-y-1.5 shadow-sm transition hover:bg-slate-100 duration-200">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="avatar placeholder">
              <div class="bg-slate-200 text-slate-700 rounded-full w-5.5 h-5.5 text-[8px] font-bold">
                <span>${initial.toUpperCase()}</span>
              </div>
            </div>
            <span class="text-xs font-bold text-slate-800">${escapeHtml(c.author.display_name)}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-[8px] opacity-40 font-mono">${new Date(c.created_at).toLocaleTimeString()}</span>
            ${isOwner ? `<button class="btn-delete-comment text-rose-600 hover:underline text-[9px] font-bold" data-id="${c.id}">Delete</button>` : ""}
          </div>
        </div>
        <p class="text-xs text-slate-700 pl-7.5 leading-normal">${escapeHtml(c.body)}</p>
      </div>
    `;
  }).join("");
}

// --- CREATE ISSUE MODAL ---
function renderCreateIssueModalContent() {
  const container = document.querySelector("#create-issue-modal-content");
  if (!container) return;
  
  const allIssues = state.board?.columns.flatMap(c => c.issues) ?? [];
  const parentCandidates = allIssues.filter(i => i.type !== "sub_task");

  container.innerHTML = `
    <div class="modal-box glass-panel-heavy max-w-lg border border-slate-300/60 rounded-2xl p-6 shadow-2xl bg-white">
      <h3 class="font-extrabold text-sm uppercase tracking-wider mb-4 text-primary font-mono-tag">Create New Project Issue</h3>
      <form id="create-issue-form" method="dialog" class="space-y-4">
        
        <div>
          <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Issue Type</label>
          <select id="create-type" class="select select-sm w-full font-semibold rounded-lg text-xs bg-slate-50">
            <option value="task">✅ Task</option>
            <option value="story">📖 Story</option>
            <option value="bug">🐛 Bug</option>
            <option value="epic">💎 Epic</option>
            <option value="sub_task">🌿 Sub-task</option>
          </select>
        </div>

        <div>
          <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Summary</label>
          <input id="create-title" type="text" required placeholder="Issue key summary..." class="input input-sm w-full font-semibold rounded-lg text-xs bg-slate-50 text-slate-800" />
        </div>

        <div>
          <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Description</label>
          <textarea id="create-desc" placeholder="Provide background logs, expectations..." class="textarea textarea-sm w-full font-medium text-xs bg-slate-50 rounded-lg text-slate-800" rows="3"></textarea>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Priority</label>
            <select id="create-priority" class="select select-sm w-full font-semibold rounded-lg text-xs bg-slate-50">
              <option value="high">🔴 High</option>
              <option value="medium" selected>🟡 Medium</option>
              <option value="low">🔵 Low</option>
            </select>
          </div>
          
          <div>
            <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Story Points</label>
            <input id="create-points" type="number" min="0" placeholder="Complexity Points..." class="input input-sm w-full font-semibold rounded-lg text-xs bg-slate-50 text-slate-800" />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Assignee</label>
            <select id="create-assignee" class="select select-sm w-full font-semibold rounded-lg text-xs bg-slate-50">
              <option value="">Unassigned</option>
              ${state.users.map(u => `<option value="${u.id}">${escapeHtml(u.display_name)}</option>`).join("")}
            </select>
          </div>
          
          <div>
            <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Sprint Cycle</label>
            <select id="create-sprint" class="select select-sm w-full font-semibold rounded-lg text-xs bg-slate-50">
              <option value="">Backlog (No Sprint)</option>
              ${state.sprints.map(s => `<option value="${s.id}">${escapeHtml(s.name)} (${s.status})</option>`).join("")}
            </select>
          </div>
        </div>

        <div id="create-parent-container" class="hidden">
          <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Parent link</label>
          <select id="create-parent" class="select select-sm w-full font-semibold rounded-lg text-xs bg-slate-50">
            <option value="">No Parent</option>
            ${parentCandidates.map(p => `<option value="${p.id}">${p.issue_key} - ${escapeHtml(p.title)}</option>`).join("")}
          </select>
        </div>

        <div class="modal-action flex justify-between border-t border-slate-100 pt-4">
          <button type="button" id="btn-cancel-create" class="btn btn-sm btn-ghost text-xs rounded-lg">Cancel</button>
          <button type="submit" id="btn-submit-create" class="btn btn-sm btn-primary font-bold rounded-lg text-xs text-white">Create Issue</button>
        </div>
      </form>
    </div>
  `;

  const typeSelect = document.querySelector("#create-type") as HTMLSelectElement;
  const parentContainer = document.querySelector("#create-parent-container");
  
  typeSelect?.addEventListener("change", () => {
    if (typeSelect.value === "sub_task") {
      parentContainer?.classList.remove("hidden");
    } else {
      parentContainer?.classList.add("hidden");
    }
  });

  document.querySelector("#btn-cancel-create")?.addEventListener("click", () => {
    document.querySelector<HTMLDialogElement>("#create-issue-modal")?.close();
  });

  document.querySelector("#create-issue-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const type = typeSelect.value;
    const title = (document.querySelector("#create-title") as HTMLInputElement).value;
    const description = (document.querySelector("#create-desc") as HTMLTextAreaElement).value;
    const priority = (document.querySelector("#create-priority") as HTMLSelectElement).value;
    const assigneeId = (document.querySelector("#create-assignee") as HTMLSelectElement).value || undefined;
    const sprintId = (document.querySelector("#create-sprint") as HTMLSelectElement).value || undefined;
    const parentId = (document.querySelector("#create-parent") as HTMLSelectElement).value || undefined;
    const pointsText = (document.querySelector("#create-points") as HTMLInputElement).value;
    
    const story_points = pointsText !== "" ? parseInt(pointsText, 10) : undefined;
    
    try {
      await request(`/api/projects/${projectId()}/issues?${userParam()}`, {
        method: "POST",
        body: JSON.stringify({
          type,
          title,
          description: description || undefined,
          priority,
          assignee_id: assigneeId,
          sprint_id: sprintId,
          parent_id: type === "sub_task" ? parentId : undefined,
          story_points,
          reporter_id: state.users.find(u => u.username === state.activeUser)?.id,
        }),
      });
      showToast("Issue successfully created", "success");
      document.querySelector<HTMLDialogElement>("#create-issue-modal")?.close();
      await loadAllData(true);
      renderWorkspace();
    } catch (err: any) {
      console.error(err);
      showToast(`Failed to create issue: ${err.body?.detail?.message || err.status}`, "error");
    }
  });
}

// --- CREATE SPRINT MODAL ---
function setupCreateSprintModal() {
  const form = document.querySelector("#create-sprint-form");
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = (document.querySelector("#sprint-name") as HTMLInputElement).value;
    const startVal = (document.querySelector("#sprint-start") as HTMLInputElement).value;
    const endVal = (document.querySelector("#sprint-end") as HTMLInputElement).value;
    
    try {
      await request(`/api/projects/${projectId()}/sprints?${userParam()}`, {
        method: "POST",
        body: JSON.stringify({
          name,
          start_date: startVal || null,
          end_date: endVal || null,
        }),
      });
      showToast("Planned sprint successfully created", "success");
      document.querySelector<HTMLDialogElement>("#create-sprint-modal")?.close();
      (document.querySelector("#sprint-name") as HTMLInputElement).value = "";
      (document.querySelector("#sprint-start") as HTMLInputElement).value = "";
      (document.querySelector("#sprint-end") as HTMLInputElement).value = "";
      await loadAllData(true);
      renderWorkspace();
    } catch (err: any) {
      showToast("Failed to create sprint. Admin credentials required.", "error");
    }
  });
  
  document.querySelector("#btn-cancel-create-sprint")?.addEventListener("click", () => {
    document.querySelector<HTMLDialogElement>("#create-sprint-modal")?.close();
  });
}

// --- COMPLETE SPRINT MODAL ---
function openCompleteSprintModal(sprintId: string) {
  const modal = document.querySelector<HTMLDialogElement>("#complete-sprint-modal");
  const container = document.querySelector("#complete-sprint-modal-content");
  if (!modal || !container) return;

  const allIssues = state.board?.columns.flatMap(c => c.issues) ?? [];
  const activeIssues = allIssues.filter(i => i.sprint?.id === sprintId);
  const incompleteIssues = activeIssues.filter(i => i.status !== "Done");
  const nextSprints = state.sprints.filter(s => s.id !== sprintId && s.status === "planned");

  container.innerHTML = `
    <h3 class="font-extrabold text-sm uppercase tracking-wider mb-4 text-primary font-mono-tag">Complete Sprint Cycle</h3>
    
    <div class="space-y-4">
      <p class="text-xs opacity-75">
        Completing this sprint will freeze its velocity calculations. There are currently 
        <span class="font-bold text-warning">${incompleteIssues.length}</span> incomplete issues.
      </p>

      ${incompleteIssues.length > 0 ? `
        <div>
          <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-40 block mb-2 font-mono-tag">Move Incomplete Issues To:</label>
          <select id="complete-carry-target" class="select select-sm select-bordered w-full font-semibold bg-slate-50 rounded-lg text-xs">
            <option value="">Global Backlog</option>
            ${nextSprints.map(s => `<option value="${s.id}">${escapeHtml(s.name)} (Planned)</option>`).join("")}
          </select>
        </div>
        
        <div class="max-h-40 overflow-y-auto custom-scrollbar border border-slate-200 bg-slate-50 rounded-xl p-2 space-y-2">
          ${incompleteIssues.map(issue => `
            <div class="flex justify-between items-center text-xs p-1">
              <span class="font-bold opacity-80 text-[10px] font-mono-tag">${issue.issue_key}</span>
              <span class="truncate max-w-[200px] font-semibold text-slate-800">${escapeHtml(issue.title)}</span>
              <span class="badge ${statusTone(issue.status)} font-bold text-[8px] rounded px-1">${issue.status}</span>
            </div>
          `).join("")}
        </div>
      ` : `<p class="text-xs text-emerald-600 font-bold">Awesome! All issues in this sprint are completed!</p>`}

      <div class="modal-action flex justify-between mt-6 border-t border-slate-200 pt-4">
        <button type="button" id="btn-cancel-complete" class="btn btn-sm btn-ghost rounded-lg text-xs">Cancel</button>
        <button type="button" id="btn-submit-complete" class="btn btn-sm btn-error font-bold rounded-lg text-xs text-white">Complete Sprint</button>
      </div>
    </div>
  `;

  modal.showModal();

  document.querySelector("#btn-cancel-complete")?.addEventListener("click", () => {
    modal.close();
  });

  document.querySelector("#btn-submit-complete")?.addEventListener("click", async () => {
    const carryTarget = document.querySelector("#complete-carry-target") as HTMLSelectElement | null;
    const nextSprintId = carryTarget?.value || null;
    const carryOverIds = incompleteIssues.map(i => i.id);
    
    try {
      const result = await request<any>(`/api/sprints/${sprintId}/complete?${userParam()}`, {
        method: "POST",
        body: JSON.stringify({
          carry_over_issue_ids: carryOverIds,
          next_sprint_id: nextSprintId,
        }),
      });
      
      showToast(`Sprint Completed! Registered Velocity: ${result.velocity} SP`, "success");
      modal.close();
      await loadAllData(true);
      renderWorkspace();
    } catch (err: any) {
      showToast(`Failed to complete sprint: ${err.body?.detail?.message || err.status}`, "error");
    }
  });
}

// --- BOOTSTRAP INITIALIZATION ---
async function initApp() {
  const app = document.querySelector("#app");
  if (!app) return;
  
  app.innerHTML = `
    <!-- Top Level Dashboard Grid Shell -->
    <div class="min-h-screen p-4 lg:p-6 space-y-6 signal-grid">
      <!-- Navbar Mount -->
      <header id="navbar-container"></header>

      <!-- Main Workspace Section Split -->
      <div class="grid grid-cols-1 xl:grid-cols-[1.58fr_0.42fr] gap-6 items-start">
        
        <!-- Tab pages go here -->
        <main id="workspace-container" class="flex-1"></main>

        <!-- Sidebar telemetry connection feeds -->
        <aside class="glass-panel p-5 rounded-2xl shadow-sm space-y-4 bg-white border border-slate-200">
          <div>
            <h3 class="text-xs font-extrabold uppercase tracking-widest text-primary flex items-center gap-2 font-mono-tag">
              <span class="relative flex h-2 w-2">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
              </span>
              Telemetry Events
            </h3>
            <p class="text-[9px] text-slate-450 mt-1 font-medium">Real-time board workspace synchronization log</p>
          </div>
          <div id="ws-events-list" class="max-h-80 overflow-y-auto custom-scrollbar pr-2 space-y-1">
            <!-- Populated dynamically -->
          </div>
        </aside>
      </div>
    </div>

    <!-- Right Slide-Out Sidebar Drawer for issue details -->
    <div id="detail-drawer" class="fixed inset-y-0 right-0 w-full md:w-3/4 lg:w-2/3 xl:w-1/2 bg-white/95 border-l border-slate-200 shadow-2xl transition-transform duration-300 ease-in-out transform translate-x-full z-40 backdrop-blur-md">
      <div id="detail-drawer-content" class="h-full"></div>
    </div>

    <!-- Modals Container -->
    <dialog id="create-issue-modal" class="modal">
      <div id="create-issue-modal-content"></div>
    </dialog>

    <dialog id="create-sprint-modal" class="modal">
      <div class="modal-box glass-panel-heavy max-w-sm border border-slate-200 rounded-2xl p-6 shadow-xl bg-white">
        <h3 class="font-extrabold text-sm uppercase tracking-wider mb-4 text-primary font-mono-tag">Create Sprint Cycle</h3>
        <form id="create-sprint-form" class="space-y-4">
          <div>
            <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Sprint Name</label>
            <input id="sprint-name" type="text" required placeholder="Sprint name..." class="input input-sm w-full font-semibold rounded-lg text-xs bg-slate-50 text-slate-800" />
          </div>
          <div>
            <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">Start Date</label>
            <input id="sprint-start" type="date" class="input input-sm w-full font-semibold rounded-lg text-xs bg-slate-50 text-slate-800" />
          </div>
          <div>
            <label class="text-[9px] uppercase tracking-wider font-extrabold opacity-50 block mb-1.5 font-mono-tag text-slate-500">End Date</label>
            <input id="sprint-end" type="date" class="input input-sm w-full font-semibold rounded-lg text-xs bg-slate-50 text-slate-800" />
          </div>
          <div class="modal-action flex justify-between border-t border-slate-100 pt-4">
            <button type="button" id="btn-cancel-create-sprint" class="btn btn-sm btn-ghost text-xs rounded-lg">Cancel</button>
            <button type="submit" id="btn-submit-create-sprint" class="btn btn-sm btn-primary font-bold rounded-lg text-xs text-white">Create Sprint</button>
          </div>
        </form>
      </div>
    </dialog>

    <dialog id="complete-sprint-modal" class="modal">
      <div id="complete-sprint-modal-content" class="modal-box glass-panel-heavy border border-slate-200 rounded-2xl p-6 shadow-xl bg-white"></div>
    </dialog>

    <!-- Global Toast notification stacking mount -->
    <div id="toast-container" class="toast toast-top toast-end z-[100] gap-2 p-4"></div>
  `;

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDetailDrawer();
    }
  });

  setupCreateSprintModal();
}

// --- MAIN RUNTIME ---
async function start() {
  await initApp();
  await loadAllData();
  renderNavbar();
  renderWorkspace();
  connectWebSocket();
}

start().catch(err => {
  console.error("Boot critical failure", err);
});
