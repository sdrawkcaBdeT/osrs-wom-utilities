package com.example;

import com.google.inject.Provides;
import javax.inject.Inject;
import net.runelite.api.*;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.events.*;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.events.NpcLootReceived;
import net.runelite.client.game.ItemStack;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import net.runelite.client.ui.overlay.OverlayManager;
import net.runelite.api.events.AnimationChanged;
import okhttp3.*;

import java.io.IOException;
import java.util.Collection;
import java.util.HashSet;
import java.util.Set;

@PluginDescriptor(
        name = "BBD Tracker"
)
public class BBDTrackerPlugin extends Plugin
{
    @Inject
    private Client client;

    @Inject
    private BBDTrackerConfig config;

    @Inject
    private OkHttpClient httpClient;

    @Inject
    private OverlayManager overlayManager;

    @Inject
    private BBDShinyOverlay shinyOverlay;

    // --- CONFIGURATION ---
    private static final int MIN_X = 1608;
    private static final int MAX_X = 1625;
    private static final int MIN_Y = 10085;
    private static final int MAX_Y = 10104;
    private static final String SERVER_URL = "http://127.0.0.1:5000/event";
    public static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private int lastReportedHp = -1;
    private boolean wasInCombat = false;

    private boolean wasInZone = false;
    private NPC lastInteractedNpc = null;

    // --- SHINY TRACKER ---
    private final Set<NPC> shinyDragons = new HashSet<>();
    private short[] originalColors = null;

    public Set<NPC> getShinyDragons() {
        return shinyDragons;
    }

    @Provides
    BBDTrackerConfig provideConfig(ConfigManager configManager)
    {
        return configManager.getConfig(BBDTrackerConfig.class);
    }

    @Override
    protected void startUp()
    {
        overlayManager.add(shinyOverlay);
    }

    @Override
    protected void shutDown()
    {
        overlayManager.remove(shinyOverlay);
        if (!shinyDragons.isEmpty()) {
            recolorBBDModel(shinyDragons.iterator().next(), false);
        }
        shinyDragons.clear();
    }

    @Subscribe
    public void onCommandExecuted(CommandExecuted commandExecuted)
    {
        if (commandExecuted.getCommand().equals("honk"))
        {
            sendPayload("notification", "{ \"type\": \"kill\" }");
        }
    }

    @Subscribe
    public void onGameTick(GameTick tick)
    {
        if (client.getLocalPlayer() == null) return;
        boolean currentlyInZone = isPlayerInZone(client.getLocalPlayer());

        if (currentlyInZone && !wasInZone) {
            for (Player p : client.getPlayers()) processPlayerSighting(p);
        }
        if (currentlyInZone != wasInZone) {
            sendPayload("phase_change", "{ \"in_zone\": " + currentlyInZone + " }");
        }
        wasInZone = currentlyInZone;

        // Capture who we are fighting right now
        Actor target = client.getLocalPlayer().getInteracting();
        if (target instanceof NPC) {
            lastInteractedNpc = (NPC) target;
        }

        // --- LIVE HP TRACKING ---
        boolean fightingBBD = false;

        // Use lastInteractedNpc so the bar doesn't vanish if you drink a potion!
        if (lastInteractedNpc != null) {
            String name = lastInteractedNpc.getName();

            if (name != null && name.toLowerCase().contains("brutal black dragon")) {

                // If the dragon is dead, turn off the bar
                if (lastInteractedNpc.isDead() || lastInteractedNpc.getHealthRatio() == 0) {
                    fightingBBD = false;
                } else {
                    fightingBBD = true;
                    int ratio = lastInteractedNpc.getHealthRatio();
                    int scale = lastInteractedNpc.getHealthScale();

                    // If health data is available (scale > 0)
                    if (ratio > -1 && scale > 0) {
                        // BBD Max HP is exactly 315.
                        int currentHp = (int) Math.ceil(((double) ratio / scale) * 315);

                        if (currentHp != lastReportedHp) {
                            sendPayload("hp_update", String.format("{ \"current\": %d, \"max\": 315, \"active\": true }", currentHp));
                            lastReportedHp = currentHp;
                            wasInCombat = true;
                        }
                    }
                }
            }
        }

        // If we killed it or walked away, hide the bar
        if (!fightingBBD && wasInCombat) {
            sendPayload("hp_update", "{ \"current\": 0, \"max\": 315, \"active\": false }");
            lastReportedHp = -1;
            wasInCombat = false;
            lastInteractedNpc = null; // Clear memory of the dead dragon
        }
    }



    @Subscribe
    public void onAnimationChanged(AnimationChanged event)
    {
        // 1. Only care about our own player
        if (event.getActor() != client.getLocalPlayer()) return;

        // 2. Only count attacks while inside the BBD cave zone
        if (!isPlayerInZone(client.getLocalPlayer())) return;

        int animId = event.getActor().getAnimation();

        // 3. Known Ranged Attack Animations
        // 4230 = Generic/Rune Crossbow
        // 7552 = Dragon/Armadyl Crossbow
        // 7617 = Dragon Hunter Crossbow (DHCB)
        // 7615 = Twisted Bow
        if (animId == 4230 || animId == 7552 || animId == 7617 || animId == 7615)
        {
            sendPayload("player_attack", "{}");
        }
    }

    @Subscribe
    public void onPlayerSpawned(PlayerSpawned event) {
        if (client.getLocalPlayer() != null && isPlayerInZone(client.getLocalPlayer())) {
            processPlayerSighting(event.getPlayer());
        }
    }

    private boolean isPlayerInZone(Player p) {
        if (p == null) return false;
        WorldPoint loc = p.getWorldLocation();
        return loc.getX() >= MIN_X && loc.getX() <= MAX_X && loc.getY() >= MIN_Y && loc.getY() <= MAX_Y;
    }

    private void processPlayerSighting(Player p) {
        if (p == null || p == client.getLocalPlayer() || !isPlayerInZone(p)) return;
        StringBuilder gearJson = new StringBuilder("[");
        PlayerComposition comp = p.getPlayerComposition();
        if (comp != null) {
            for (int id : comp.getEquipmentIds()) if (id > 512) gearJson.append(id - 512).append(",");
            if (gearJson.length() > 1) gearJson.setLength(gearJson.length() - 1);
        }
        gearJson.append("]");
        String payload = String.format("{ \"name\": \"%s\", \"combat\": %d, \"world\": %d, \"gear\": %s }",
                p.getName(), p.getCombatLevel(), client.getWorld(), gearJson.toString());
        sendPayload("player_spawn", payload);
    }

    // ==========================================
    // THE 3D MODEL SPAWN LOGIC
    // ==========================================
    @Subscribe
    public void onNpcSpawned(NpcSpawned event)
    {
        NPC npc = event.getNpc();
        String name = npc.getName();

        if (name != null && name.toLowerCase().contains("brutal black dragon"))
        {
            if (Math.random() <= 0.00048828125) // 1/2048 ; twice as common as a real shiny in pokemon.
            {
                shinyDragons.add(npc);
                sendPayload("shiny_spawn", "{ \"status\": \"appeared\" }");
                recolorBBDModel(npc, true);
            }
        }
    }

    @Subscribe
    public void onNpcDespawned(NpcDespawned event)
    {
        NPC npc = event.getNpc();
        if (shinyDragons.contains(npc)) {
            shinyDragons.remove(npc);

            // Revert colors if the true shiny is gone
            if (shinyDragons.isEmpty()) {
                recolorBBDModel(npc, false);
            }
        }
    }

    private void recolorBBDModel(NPC npc, boolean makeShiny) {
        NPCComposition comp = client.getNpcDefinition(npc.getId());
        if (comp == null) return;

        // Note: Change to getColorsToReplaceWith() if your RL version requires plural!
        short[] colorsToReplaceWith = comp.getColorToReplaceWith();
        if (colorsToReplaceWith == null) return;

        if (makeShiny) {
            if (originalColors == null) {
                originalColors = colorsToReplaceWith.clone();
            }

            for (int i = 0; i < colorsToReplaceWith.length; i++) {
                short orig = originalColors[i];
                int origLightness = orig & 0x7F;


//                 --- OPTION 5: Void Amethyst (Rich, Catacombs-themed purple) ---
                 int hue = 53;
                 int sat = 5;
                 int lightnessBoost = 3;


                // --- OPTION 8: Albino / Silver (Stark white contrast) ---
//                 int hue = 0; // Hue doesn't matter when saturation is 0
//                 int sat = 0; // 0 saturation forces pure grayscale
//                 int lightnessBoost = 20; // Massive boost to turn black scales into white/silver

                int finalLightness = Math.min(127, origLightness + lightnessBoost);
                colorsToReplaceWith[i] = (short) ((hue << 10) | (sat << 7) | finalLightness);
            }
        } else {
            if (originalColors != null) {
                for (int i = 0; i < colorsToReplaceWith.length; i++) {
                    colorsToReplaceWith[i] = originalColors[i];
                }
            }
        }
    }

    // ==========================================
    // THE KILL LOGIC
    // ==========================================
    @Subscribe
    public void onActorDeath(ActorDeath event)
    {
        Actor actor = event.getActor();
        if (actor instanceof NPC)
        {
            NPC npc = (NPC) actor;
            String name = npc.getName();

            if (name != null && name.toLowerCase().contains("brutal black dragon"))
            {
                Player local = client.getLocalPlayer();
                if (local == null) return;

                boolean direct = (npc.getInteracting() == local) ||
                        (local.getInteracting() == npc);

                if (direct || lastInteractedNpc == npc)
                {
                    if (shinyDragons.contains(npc)) {
                        sendPayload("notification", "{ \"type\": \"shiny_kill\" }");
                    } else {
                        sendPayload("notification", "{ \"type\": \"kill\" }");
                    }

                    if (lastInteractedNpc == npc) lastInteractedNpc = null;
                }
            }
        }
    }

    // ==========================================
    // COMBAT TELEMETRY (HITSPLATS)
    // ==========================================
    @Subscribe
    public void onHitsplatApplied(HitsplatApplied event)
    {
        // 1. We only care if a Non-Player Character is taking damage
        if (!(event.getActor() instanceof NPC)) return;

        NPC npc = (NPC) event.getActor();
        String name = npc.getName();

        if (name != null && name.toLowerCase().contains("brutal black dragon"))
        {
            Hitsplat hitsplat = event.getHitsplat();

            // 2. ONLY log the damage if WE dealt it (Filters out bot/other player damage!)
            if (hitsplat.isMine())
            {
                int damage = hitsplat.getAmount();

                // We can use the lastReportedHp from your GameTick logic to track Overkill!
                int hpBefore = lastReportedHp > 0 ? lastReportedHp : 315;

                // Send to Python
                String payload = String.format("{ \"damage\": %d, \"hp_before\": %d }", damage, hpBefore);
                sendPayload("combat_telemetry", payload);
            }
        }
    }

    @Subscribe
    public void onNpcLootReceived(NpcLootReceived event)
    {
        if (event.getNpc().getName() != null && event.getNpc().getName().toLowerCase().contains("brutal black dragon"))
        {
            StringBuilder itemsJson = new StringBuilder("[");
            for (ItemStack stack : event.getItems())
                itemsJson.append(String.format("{\"id\": %d, \"qty\": %d},", stack.getId(), stack.getQuantity()));
            if (itemsJson.length() > 1) itemsJson.setLength(itemsJson.length() - 1);
            itemsJson.append("]");
            sendPayload("loot_event", "{ \"npc\": \"Brutal Black Dragon\", \"items\": " + itemsJson.toString() + " }");
        }
    }

    private void sendPayload(String eventType, String jsonPayload)
    {
        String json = String.format("{\"event\": \"%s\", \"payload\": %s}", eventType, jsonPayload);
        RequestBody body = RequestBody.create(JSON, json);
        httpClient.newCall(new Request.Builder().url(SERVER_URL).post(body).build()).enqueue(new Callback() {
            @Override public void onFailure(Call call, IOException e) {}
            @Override public void onResponse(Call call, Response response) throws IOException { response.close(); }
        });
    }
}