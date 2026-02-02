// frontend/src/services/api.js
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function http(path, { method = "GET", json, formData } = {}) {
  const url = `${BASE_URL}${path}`;
  const headers = {};
  let body;

  if (json) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (formData) {
    body = formData;
  }

  const res = await fetch(url, { method, headers, body, credentials: "include" });

  let data;
  try {
    data = await res.json();
  } catch {
    data = { detail: await res.text() };
  }
  if (!res.ok) {
    const msg = data?.detail || data?.error || "Request failed";
    throw new Error(msg);
  }
  return data;
}

export const authAPI = {
  login: (role, employee_id) =>
    http("/api/login", { method: "POST", json: { role, employee_id } }),
};

export const queryAPI = {
  sendQuery: (question) => http("/api/query", { method: "POST", json: { question } }),
};

export const uploadAPI = {
  uploadCSV: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return http("/api/upload/csv", { method: "POST", formData: fd });
  },
  uploadPDF: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return http("/api/upload/pdf", { method: "POST", formData: fd });
  },
};

export const leaveAPI = {
  apply: ({ employee_id, start_date, end_date, days, reason }) =>
    http("/api/leave/apply", { method: "POST", json: { employee_id, start_date, end_date, days, reason } }),
  pending: () => http("/api/leave/pending"),
  decide: ({ request_id, decision, hr_actor = "HR Portal" }) =>
    http("/api/leave/decide", { method: "POST", json: { request_id, decision, hr_actor } }),
  mine: (empId) => http(`/api/leave/mine/${empId}`),
};

export const notificationsAPI = {
  getForEmployee: (empId) => http(`/api/notifications/${empId}?role=EMPLOYEE`),
  getForHR: () => http(`/api/notifications/0?role=HR`),
};
