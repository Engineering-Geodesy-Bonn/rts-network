<script lang="ts">
    import { onDestroy } from "svelte";
    import { currentSession } from "../stores/session";
    import RTSList from "./RTSList.svelte";
    import JobsTab from "./JobsTab.svelte";
    import PlotTab from "./PlotTab.svelte";
    import DevicesTab from "./DevicesTab.svelte";
    import ExternalSensorsTab from "./ExternalSensorsTab.svelte";
    import SettingsTab from "./SettingsTab.svelte";

    let activeTab = $state<
        "rts" | "jobs" | "plot" | "devices" | "externalSensors" | "settings"
    >("rts");
    let sessionName = $state("");

    const unsub = currentSession.subscribe((s) => {
        sessionName = s?.name || "";
    });

    onDestroy(unsub);

    function logout() {
        currentSession.clear();
    }

    const tabs: {
        id:
            | "rts"
            | "jobs"
            | "plot"
            | "devices"
            | "externalSensors"
            | "settings";
        label: string;
        icon: string;
    }[] = [
        { id: "rts", label: "RTS Stations", icon: "" },
        { id: "jobs", label: "Jobs", icon: "📋" },
        { id: "plot", label: "Measurements", icon: "📊" },
        { id: "devices", label: "Devices", icon: "🖥️" },
        { id: "externalSensors", label: "External Sensors", icon: "📡" },
        { id: "settings", label: "Settings", icon: "⚙️" },
    ];
</script>

<div class="min-h-screen flex flex-col">
    <!-- Header -->
    <header
        class="bg-slate-800 border-b border-slate-700 px-6 py-3 flex items-center justify-between shrink-0"
    >
        <div class="flex items-center gap-4">
            <div class="flex items-center gap-2">
                <img src="/RTS.png" alt="RTS" class="h-7 object-contain" />
                <h1 class="text-xl font-bold text-white tracking-tight">
                    RTS Dashboard
                </h1>
            </div>
            <span
                class="text-sm text-slate-400 bg-slate-700 px-3 py-1 rounded-full"
                >{sessionName}</span
            >
        </div>
        <button
            onclick={logout}
            class="text-slate-400 hover:text-white hover:bg-slate-700 px-4 py-2 rounded-lg transition-colors text-sm cursor-pointer"
        >
            ← Change Session
        </button>
    </header>

    <!-- Tab Navigation -->
    <nav class="bg-slate-800/50 border-b border-slate-700 px-6 shrink-0">
        <div class="flex gap-1">
            {#each tabs as tab (tab.id)}
                <button
                    class="px-5 py-3 text-sm font-medium transition-colors relative cursor-pointer
            {activeTab === tab.id
                        ? 'text-blue-400'
                        : 'text-slate-400 hover:text-slate-200'}"
                    onclick={() => (activeTab = tab.id)}
                >
                    <span class="flex items-center gap-1.5">
                        {#if tab.id === "rts"}
                            <img
                                src="/RTS.png"
                                alt=""
                                class="h-4 object-contain inline-block"
                            />
                        {:else}
                            {tab.icon}
                        {/if}
                        {tab.label}
                    </span>
                    {#if activeTab === tab.id}
                        <div
                            class="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500 rounded-full"
                        ></div>
                    {/if}
                </button>
            {/each}
        </div>
    </nav>

    <!-- Content -->
    <main class="flex-1 p-6 overflow-auto">
        {#if activeTab === "rts"}
            <RTSList />
        {:else if activeTab === "jobs"}
            <JobsTab />
        {:else if activeTab === "plot"}
            <PlotTab />
        {:else if activeTab === "devices"}
            <DevicesTab />
        {:else if activeTab === "externalSensors"}
            <ExternalSensorsTab />
        {:else if activeTab === "settings"}
            <SettingsTab />
        {/if}
    </main>
</div>
