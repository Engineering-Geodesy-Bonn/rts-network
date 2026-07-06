<script lang="ts">
    import { onMount } from "svelte";
    import {
        getSessions,
        createSession,
        deleteSession,
        exportSession,
    } from "../api/client";
    import { currentSession } from "../stores/session";
    import type { SessionResponse } from "../api/types";

    let sessions = $state<SessionResponse[]>([]);
    let loading = $state(true);
    let error = $state("");
    let newSessionName = $state("");
    let creating = $state(false);
    let exporting = $state(false);

    async function loadSessions() {
        loading = true;
        error = "";
        try {
            sessions = await getSessions();
        } catch (e: any) {
            error = e.message || "Failed to load sessions";
        } finally {
            loading = false;
        }
    }

    async function handleCreate() {
        if (!newSessionName.trim()) return;
        creating = true;
        error = "";
        try {
            const session = await createSession({
                name: newSessionName.trim(),
            });
            newSessionName = "";
            currentSession.select(session);
        } catch (e: any) {
            error = e.message || "Failed to create session";
        } finally {
            creating = false;
        }
    }

    async function handleDelete(id: string, event: Event) {
        event.stopPropagation();
        if (!confirm("Delete this session and all associated data?")) return;
        try {
            await deleteSession(id);
            sessions = sessions.filter((s) => s.id !== id);
        } catch (e: any) {
            error = e.message || "Failed to delete session";
        }
    }

    function handleSelect(session: SessionResponse) {
        currentSession.select(session);
    }

    async function handleExport(event: Event, sessionId: string) {
        event.stopPropagation();
        exporting = true;
        error = "";
        try {
            await exportSession(sessionId);
        } catch (e: any) {
            error = e.message || "Export failed";
        } finally {
            exporting = false;
        }
    }

    function formatDate(ts: number): string {
        return new Date(ts * 1000).toLocaleString();
    }

    onMount(() => {
        loadSessions();
    });
</script>

<div class="min-h-screen flex items-center justify-center p-4">
    <div class="w-full max-w-lg">
        <!-- Header -->
        <div class="text-center mb-8">
            <img
                src="/RTS.png"
                alt="RTS"
                class="h-20 mx-auto mb-3 object-contain"
            />
            <h1 class="text-4xl font-bold mb-2 tracking-tight">
                RTS Dashboard
            </h1>
            <p class="text-slate-400">
                Select or create a session to get started
            </p>
        </div>

        {#if error}
            <div
                class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-4 text-sm"
            >
                {error}
            </div>
        {/if}

        <!-- Create Session -->
        <div class="bg-slate-800 rounded-xl p-6 mb-6 border border-slate-700">
            <h2 class="text-lg font-semibold mb-3">New Session</h2>
            <form
                class="flex gap-3"
                onsubmit={(e) => {
                    e.preventDefault();
                    handleCreate();
                }}
            >
                <input
                    type="text"
                    bind:value={newSessionName}
                    placeholder="Session name..."
                    class="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                />
                <button
                    type="submit"
                    disabled={creating || !newSessionName.trim()}
                    class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium px-6 py-2.5 rounded-lg transition-colors cursor-pointer"
                >
                    {creating ? "Creating..." : "Create"}
                </button>
            </form>
        </div>

        <!-- Session List -->
        <div class="bg-slate-800 rounded-xl border border-slate-700">
            <div
                class="p-4 border-b border-slate-700 flex items-center justify-between"
            >
                <h2 class="text-lg font-semibold">Existing Sessions</h2>
                <button
                    class="text-xs text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
                    onclick={loadSessions}
                >
                    Refresh
                </button>
            </div>

            {#if loading}
                <div class="p-8 text-center text-slate-400">
                    <div
                        class="inline-block w-6 h-6 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"
                    ></div>
                    <p class="mt-2">Loading sessions...</p>
                </div>
            {:else if sessions.length === 0}
                <div class="p-8 text-center text-slate-500">
                    No sessions found. Create one above.
                </div>
            {:else}
                <div class="divide-y divide-slate-700">
                    {#each sessions as session (session.id)}
                        <!-- svelte-ignore a11y_no_static_element_interactions -->
                        <div
                            class="w-full flex items-center justify-between p-4 hover:bg-slate-700/50 transition-colors text-left cursor-pointer"
                            onclick={() => handleSelect(session)}
                            onkeydown={(e) =>
                                e.key === "Enter" && handleSelect(session)}
                            role="button"
                            tabindex="0"
                        >
                            <div>
                                <div class="font-medium text-white">
                                    {session.name}
                                </div>
                                <div class="text-sm text-slate-400 mt-0.5">
                                    Created {formatDate(session.created_at)} &middot;
                                    ID: {session.id}
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <button
                                    class="text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10 p-2 rounded-lg transition-colors cursor-pointer disabled:opacity-40"
                                    disabled={exporting}
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        handleExport(e, session.id);
                                    }}
                                    title="Export all session data"
                                >
                                    <svg
                                        class="w-5 h-5"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            stroke-linecap="round"
                                            stroke-linejoin="round"
                                            stroke-width="2"
                                            d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                                        />
                                    </svg>
                                </button>
                                <button
                                    class="text-red-400 hover:text-red-300 hover:bg-red-500/10 p-2 rounded-lg transition-colors cursor-pointer"
                                    onclick={(e) => handleDelete(session.id, e)}
                                    title="Delete session"
                                >
                                    <svg
                                        class="w-5 h-5"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            stroke-linecap="round"
                                            stroke-linejoin="round"
                                            stroke-width="2"
                                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                        />
                                    </svg>
                                </button>
                                <svg
                                    class="w-5 h-5 text-slate-500"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        stroke-linecap="round"
                                        stroke-linejoin="round"
                                        stroke-width="2"
                                        d="M9 5l7 7-7 7"
                                    />
                                </svg>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </div>
    </div>
</div>
