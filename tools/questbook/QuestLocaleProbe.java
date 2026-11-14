import dev.ftb.mods.ftblibrary.snbt.SNBT;
import dev.ftb.mods.ftbquests.util.TextUtils;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import net.minecraft.client.resources.language.ClientLanguage;
import net.minecraft.client.resources.language.I18n;
import net.minecraft.client.resources.language.LanguageInfo;
import net.minecraft.locale.Language;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.StringTag;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.TranslatableComponent;
import net.minecraft.server.packs.FolderPackResources;
import net.minecraft.server.packs.PackType;
import net.minecraft.server.packs.resources.MultiPackResourceManager;

public final class QuestLocaleProbe {
    private static final Pattern KEY = Pattern.compile(
        "(?:^\\{|\"translate\":\")(inferno_quests\\.[a-z0-9_.]+)(?:\\}|\"})$");
    private static final String QUESTS = "config/ftbquests/quests";
    private static final List<String> DISPLAY = List.of("title", "subtitle", "description", "hover");

    public static void main(String[] args) throws Exception {
        Path author = Path.of(args[0]);
        Path localized = Path.of(args[1]);
        List<Path> paths;
        try (var stream = Files.walk(author.resolve(QUESTS))) {
            paths = stream.filter(path -> path.toString().endsWith(".snbt")).sorted().toList();
        }
        for (String code : List.of("en_us", "ru_ru", "en_us")) {
            selectLanguage(localized, code);
            int count = 0;
            int changed = 0;
            for (Path original : paths) {
                Path replacement = localized.resolve(author.relativize(original));
                CompoundTag english = SNBT.read(original);
                CompoundTag localizedData = SNBT.read(Files.isRegularFile(replacement) ? replacement : original);
                Totals result = new Totals(code);
                compare(english, localizedData, "", result);
                count += result.total;
                changed += result.changed;
            }
            if (count != Language.m_128107_().getLanguageData().size()
                    || (code.equals("ru_ru") ? changed == 0 : changed != 0)) {
                throw new IllegalStateException("Unexpected localized coverage " + count + "/" + changed);
            }
            System.out.println(code + " PASS, " + paths.size() + " SNBT files, "
                    + count + " localized fields, " + changed + " visibly different strings");
        }
    }

    private static void selectLanguage(Path root, String code) throws Exception {
        var languages = new ArrayList<LanguageInfo>();
        languages.add(new LanguageInfo("en_us", "US", "English", false));
        if (code.equals("ru_ru")) languages.add(new LanguageInfo("ru_ru", "Россия", "Русский", false));
        try (var resources = new MultiPackResourceManager(PackType.CLIENT_RESOURCES,
                List.of(new FolderPackResources(root.resolve("kubejs").toFile())))) {
            var language = ClientLanguage.m_118916_(resources, languages);
            Language.m_128114_(language);
            Method setI18n = I18n.class.getDeclaredMethod("m_118941_", Language.class);
            setI18n.setAccessible(true);
            setI18n.invoke(null, language);
        }
    }

    private static void compare(Tag before, Tag after, String field, Totals result) {
        if (before instanceof CompoundTag old && after instanceof CompoundTag current) {
            if (!old.m_128431_().equals(current.m_128431_())) throw new IllegalStateException("SNBT keys changed");
            for (String key : old.m_128431_()) compare(old.m_128423_(key), current.m_128423_(key), key, result);
        } else if (before instanceof ListTag old && after instanceof ListTag current) {
            if (old.size() != current.size()) throw new IllegalStateException("SNBT list length changed");
            for (int i = 0; i < old.size(); i++) compare(old.get(i), current.get(i), field, result);
        } else if (!before.equals(after)) {
            if (!DISPLAY.contains(field) || !(before instanceof StringTag old) || !(after instanceof StringTag current)) {
                throw new IllegalStateException("Unexpected mechanics change: " + field);
            }
            var key = KEY.matcher(current.m_7916_());
            if (!key.find() || !Language.m_128107_().m_6722_(key.group(1))) {
                throw new IllegalStateException("Missing quest language key: " + current);
            }
            Component original = field.equals("hover") ? new net.minecraft.network.chat.TextComponent(old.m_7916_())
                    : TextUtils.parseRawText(old.m_7916_());
            Component resolved = field.equals("hover") ? new TranslatableComponent(key.group(1))
                    : TextUtils.parseRawText(current.m_7916_());
            String text = resolved.getString();
            if (text.isBlank() || text.contains("inferno_quests.") || text.contains("Invalid formatting!")
                    || text.contains("Exception:")) {
                throw new IllegalStateException("Quest string failed to render: " + key.group(1) + " " + text);
            }
            if (result.locale.equals("en_us")) {
                // Compare the resolved style and text, regardless of the component tree shape.
                if (!styled(original).equals(styled(resolved))) {
                    throw new IllegalStateException("English fallback changed: " + key.group(1) + " "
                            + original.getString() + " -> " + text);
                }
            }
            result.total++;
            if (!text.equals(original.getString())) result.changed++;
        }
    }

    private static List<Object> styled(Component value) {
        var flattened = new ArrayList<>();
        value.m_7451_((style, text) -> {
            text.codePoints().forEach(code -> flattened.add(List.of(style, code)));
            return java.util.Optional.empty();
        }, net.minecraft.network.chat.Style.f_131099_);
        return flattened;
    }

    private static final class Totals {
        private final String locale;
        private int total;
        private int changed;

        private Totals(String locale) {
            this.locale = locale;
        }
    }
}
