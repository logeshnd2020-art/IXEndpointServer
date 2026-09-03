/**
 * Shared client-side auth helper for IX Endpoint Services.
 *
 * Tokens are issued by the existing server-side JWT system
 * (POST /api/auth/login, POST /api/auth/refresh) and stored in
 * localStorage. Every dashboard page includes this file, calls
 * IXAuth.requireAuth() once on load, and uses IXAuth.authFetch(...)
 * instead of the raw fetch() for every API call so requests always carry
 * a bearer token and transparently retry once after a silent refresh.
 */
const IXAuth = (() => {
    const ACCESS_KEY = "ix_access_token";
    const REFRESH_KEY = "ix_refresh_token";
    const USER_KEY = "ix_user";

    function getAccessToken() {
        return localStorage.getItem(ACCESS_KEY);
    }

    function getRefreshToken() {
        return localStorage.getItem(REFRESH_KEY);
    }

    function getUser() {
        const raw = localStorage.getItem(USER_KEY);
        return raw ? JSON.parse(raw) : null;
    }

    function isLoggedIn() {
        return !!getAccessToken();
    }

    function storeSession(data) {
        localStorage.setItem(ACCESS_KEY, data.access_token);
        if (data.refresh_token) {
            localStorage.setItem(REFRESH_KEY, data.refresh_token);
        }
        if (data.user) {
            localStorage.setItem(USER_KEY, JSON.stringify(data.user));
        }
    }

    function clearSession() {
        localStorage.removeItem(ACCESS_KEY);
        localStorage.removeItem(REFRESH_KEY);
        localStorage.removeItem(USER_KEY);
    }

    async function login(usernameOrEmail, password) {
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username_or_email: usernameOrEmail,
                password: password,
            }),
        });

        if (!response.ok) {
            // Deliberately generic -- never reveal whether the username
            // or the password was the one that was wrong.
            throw new Error("Invalid username or password.");
        }

        const data = await response.json();
        storeSession(data);
        return data.user;
    }

    function logout() {
        clearSession();
        window.location.href = "/login";
    }

    function requireAuth() {
        if (!isLoggedIn()) {
            window.location.href = "/login";
        }
    }

    async function tryRefresh() {
        const refreshToken = getRefreshToken();
        if (!refreshToken) {
            return false;
        }

        try {
            const response = await fetch("/api/auth/refresh", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ refresh_token: refreshToken }),
            });

            if (!response.ok) {
                return false;
            }

            const data = await response.json();
            localStorage.setItem(ACCESS_KEY, data.access_token);
            return true;
        } catch (err) {
            return false;
        }
    }

    async function authFetch(url, options = {}) {
        const doFetch = () => {
            const headers = Object.assign({}, options.headers || {}, {
                Authorization: `Bearer ${getAccessToken()}`,
            });
            return fetch(url, Object.assign({}, options, { headers }));
        };

        let response = await doFetch();

        if (response.status === 401) {
            const refreshed = await tryRefresh();
            if (refreshed) {
                response = await doFetch();
            } else {
                clearSession();
                window.location.href = "/login";
                return response;
            }
        }

        return response;
    }

    return {
        getAccessToken,
        getUser,
        isLoggedIn,
        login,
        logout,
        requireAuth,
        authFetch,
    };
})();
