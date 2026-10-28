<script lang="ts">
    import { onDestroy } from "svelte";
    import { currentSession } from "../stores/session";
    import RTSList from "./RTSList.svelte";
    import JobsTab from "./JobsTab.svelte";
    import PlotTab from "./PlotTab.svelte";
    import DevicesTab from "./DevicesTab.svelte";
    import ExternalSensorsTab from "./ExternalSensorsTab.svelte";
    import SynchronizerTab from "./SynchronizerTab.svelte";
    import SettingsTab from "./SettingsTab.svelte";

    let activeTab = $state<
        | "rts"
        | "jobs"
        | "plot"
        | "devices"
        | "externalSensors"
        | "synchronizer"
        | "settings"
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
            | "synchronizer"
            | "settings";
        label: string;
        shortLabel: string;
        icon: string;
    }[] = [
        { id: "rts", label: "RTS Stations", shortLabel: "RTS", icon: "" },
        { id: "jobs", label: "Jobs", shortLabel: "Jobs", icon: "📋" },
        { id: "plot", label: "Measurements", shortLabel: "Plots", icon: "📊" },
        { id: "devices", label: "Devices", shortLabel: "Devices", icon: "🖥️" },
        {
            id: "externalSensors",
            label: "External Sensors",
            shortLabel: "Sensors",
            icon: "📡",
        },
        {
            id: "synchronizer",
            label: "Synchronizer",
            shortLabel: "Sync",
            icon: "🔄",
        },
        {
            id: "settings",
            label: "Settings",
            shortLabel: "Settings",
            icon: "⚙️",
        },
    ];

    function selectTab(id: (typeof tabs)[number]["id"]) {
        activeTab = id;
        window.scrollTo({ top: 0 });
    }
</script>

<div class="min-h-screen flex flex-col">
    <!-- Header -->
    <header
        class="bg-slate-800 border-b border-slate-700 px-3 sm:px-6 py-2 sm:py-3 pt-[max(0.5rem,env(safe-area-inset-top))] sm:pt-3 flex items-center justify-between gap-3 shrink-0"
    >
        <div class="flex items-center gap-2 sm:gap-4 min-w-0">
            <div class="flex items-center gap-2 shrink-0">
                <img
                    src="/RTS.png"
                    alt="RTS"
                    class="h-6 sm:h-7 object-contain"
                />
                <h1
                    class="text-base sm:text-xl font-bold text-white tracking-tight"
                >
                    <span class="hidden min-[400px]:inline">RTS&nbsp;</span>Dashboard
                </h1>
            </div>
            <span
                class="text-xs sm:text-sm text-slate-400 bg-slate-700 px-2.5 sm:px-3 py-1 rounded-full truncate min-w-0"
                title={sessionName}>{sessionName}</span
            >
        </div>
        <button
            onclick={logout}
            class="text-slate-400 hover:text-white hover:bg-slate-700 px-3 sm:px-4 py-2 rounded-lg transition-colors text-sm cursor-pointer shrink-0 whitespace-nowrap"
            title="Change Session"
        >
            ← <span class="hidden sm:inline">Change&nbsp;</span>Session
        </button>
    </header>

    <!-- Tab Navigation (md and up) -->
    <nav
        class="hidden md:block bg-slate-800/50 border-b border-slate-700 px-6 shrink-0"
    >
        <div class="flex gap-1 overflow-x-auto">
            {#each tabs as tab (tab.id)}
                <button
                    class="px-5 py-3 text-sm font-medium transition-colors relative cursor-pointer whitespace-nowrap
            {activeTab === tab.id
                        ? 'text-blue-400'
                        : 'text-slate-400 hover:text-slate-200'}"
                    onclick={() => selectTab(tab.id)}
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
    <main
        class="flex-1 min-w-0 px-3 pt-3 sm:px-6 sm:pt-6 pb-[calc(4.5rem+env(safe-area-inset-bottom))] md:pb-6"
    >
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
        {:else if activeTab === "synchronizer"}
            <SynchronizerTab />
        {:else if activeTab === "settings"}
            <SettingsTab />
        {/if}
    </main>

    <!-- Bottom Tab Navigation (mobile) -->
    <nav
        class="md:hidden fixed bottom-0 inset-x-0 z-40 bg-slate-800 border-t border-slate-700 pb-[env(safe-area-inset-bottom)]"
    >
        <div class="grid grid-cols-7">
            {#each tabs as tab (tab.id)}
                <button
                    class="relative flex flex-col items-center justify-center gap-0.5 min-h-14 px-0.5 py-1.5 cursor-pointer transition-colors
                        {activeTab === tab.id
                        ? 'text-blue-400 bg-slate-700/40'
                        : 'text-slate-400 active:bg-slate-700/40'}"
                    onclick={() => selectTab(tab.id)}
                    aria-label={tab.label}
                    aria-current={activeTab === tab.id ? "page" : undefined}
                >
                    {#if activeTab === tab.id}
                        <div
                            class="absolute top-0 left-2 right-2 h-0.5 bg-blue-500 rounded-full"
                        ></div>
                    {/if}
                    <span class="h-5 flex items-center text-base leading-none">
                        {#if tab.id === "rts"}
                            <img
                                src="/RTS.png"
                                alt=""
                                class="h-5 object-contain"
                            />
                        {:else}
                            {tab.icon}
                        {/if}
                    </span>
                    <span
                        class="text-[10px] leading-tight font-medium truncate max-w-full"
                        >{tab.shortLabel}</span
                    >
                </button>
            {/each}
        </div>
    </nav>
</div>
