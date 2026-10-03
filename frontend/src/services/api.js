const API_BASE_URL = 'http://127.0.0.1:8000'

export async function apiRequest(endpoint, options = {}) {
    const token = localStorage.getItem('access_token')

    const headers = {
        ...(options.headers || {}),
    }

    if (token) {
        headers.Authorization = `Bearer ${token}`
    }

    if (options.body && !(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json'
    }

    const response = await fetch(
        `${API_BASE_URL}${endpoint}`,
        {
            ...options,
            headers,
        }
    )

    const data = await response.json().catch(() => null)

    if (!response.ok) {
        if (response.status === 401) {
            localStorage.removeItem('access_token')
            localStorage.removeItem('user')
        }

        throw new Error(
            data?.detail || 'Something went wrong. Please try again.'
        )
    }

    return data
}