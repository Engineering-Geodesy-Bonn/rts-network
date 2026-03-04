<script lang="ts">
    import { onDestroy } from "svelte";
    import { apiUrl } from "../stores/apiSettings";
    import { ping } from "../api/client";

    let url = $state("");
    let testing = $state(false);
    let testResult = $state<"success" | "error" | null>(null);
    let testMessage = $state("");

    const unsub = apiUrl.subscribe((u) => {
        url = u;
    });

    onDestroy(unsub);

    function handleSave() {
        apiUrl.set(url.replace(/\/+$/, ""));
        testResult = "success";
        testMessage = "API URL saved";
        setTimeout(() => {
            testResult = null;
        }, 3000);
    }

    async function handleTest() {
        testing = true;
        testResult = null;
        // Temporarily set URL so the ping uses it
        const prevUrl = url;
        localStorage.setItem("rts-api-url", url.replace(/\/+$/, ""));
        try {
            await ping();
            testResult = "success";
            testMessage = "Connection successful!";
        } catch (e: any) {
            testResult = "error";
            testMessage = e.message || "Connection failed";
            // Restore previous URL on failure
            localStorage.setItem("rts-api-url", prevUrl);
        } finally {
            testing = false;
        }
    }

    function handleReset() {
        apiUrl.reset();
        url = "/api";
        testResult = "success";
        testMessage = "Reset to default";
        setTimeout(() => {
            testResult = null;
        }, 3000);
    }
</script>

<div class="max-w-2xl mx-auto">
    <h2 class="text-2xl font-bold mb-6">API Settings</h2>

    <div class="bg-slate-800 rounded-xl border border-slate-700 p-6">
        <div class="space-y-4">
            <div>
                <label
                    class="block text-sm font-medium text-slate-300 mb-2"
                    for="api-url">API Base URL</label
                >
                <input
                    id="api-url"
                    type="text"
                    bind:value={url}
                    placeholder="/api"
                    class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white font-mono text-sm focus:outline-none focus:border-blue-500 transition-colors"
                />
                <p class="mt-1.5 text-xs text-slate-500">
                    Use <code class="text-slate-400">/api</code> for the Vite
                    proxy, or a full URL like
                    <code class="text-slate-400">http://host:8000</code> for direct
                    access
                </p>
            </div>

            {#if testResult}
                <div
                    class="{testResult === 'success'
                        ? 'bg-green-500/10 border-green-500/30 text-green-400'
                        : 'bg-red-500/10 border-red-500/30 text-red-400'} border px-4 py-3 rounded-lg text-sm"
                >
                    {testMessage}
                </div>
            {/if}

            <div class="flex gap-3 pt-2">
                <button
                    onclick={handleTest}
                    disabled={testing}
                    class="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white font-medium px-5 py-2.5 rounded-lg transition-colors cursor-pointer"
                >
                    {testing ? "Testing..." : "Test Connection"}
                </button>
                <button
                    onclick={handleSave}
                    class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2.5 rounded-lg transition-colors cursor-pointer"
                >
                    Save
                </button>
                <button
                    onclick={handleReset}
                    class="text-slate-400 hover:text-white px-5 py-2.5 rounded-lg transition-colors cursor-pointer"
                >
                    Reset to Default
                </button>
            </div>
        </div>
    </div>

    <div class="bg-slate-800 rounded-xl border border-slate-700 p-6 mt-6">
        <h3 class="font-semibold mb-3">About</h3>
        <div class="text-sm text-slate-400 space-y-1">
            <p>
                <span class="text-white font-medium">RTS Dashboard</span> — Svelte
                Frontend
            </p>
            <p>
                Connects to the Robotic Total Station API for managing RTS
                devices, sessions, and live measurement visualization.
            </p>
        </div>
    </div>

    <!-- Keyboard shortcuts reference -->
    <div class="bg-slate-800 rounded-xl border border-slate-700 p-6 mt-6">
        <h3 class="font-semibold mb-3">API Endpoints</h3>
        <div class="text-sm text-slate-400 space-y-2 font-mono">
            <div class="flex justify-between">
                <span>Health Check</span>
                <span class="text-slate-300">GET /ping</span>
            </div>
            <div class="flex justify-between">
                <span>Sessions</span>
                <span class="text-slate-300">GET/POST /session</span>
            </div>
            <div class="flex justify-between">
                <span>RTS Stations</span>
                <span class="text-slate-300">GET/POST /rts</span>
            </div>
            <div class="flex justify-between">
                <span>Latest Measurements</span>
                <span class="text-slate-300">GET /measurements/latest</span>
            </div>
            <div class="flex justify-between">
                <span>Jobs</span>
                <span class="text-slate-300">GET/POST /jobs</span>
            </div>
            <div class="flex justify-between">
                <span>Devices</span>
                <span class="text-slate-300">GET /devices</span>
            </div>
        </div>
    </div>
</div>
