using System;
using System.Collections.Generic;

namespace XUILab.ListLab
{
    public sealed class ListItem
    {
        public readonly long Id;
        public readonly int Template;
        public readonly string Label;
        public ListItem(long id, int template, string label)
        {
            if (template < 0 || template > 1) throw new ArgumentOutOfRangeException(nameof(template));
            Id = id; Template = template; Label = label ?? throw new ArgumentNullException(nameof(label));
        }
        public static ListItem[] Generate(int count, bool dual = false)
        {
            if (count < 0) throw new ArgumentOutOfRangeException(nameof(count));
            var items = new ListItem[count];
            for (int i = 0; i < count; i++) items[i] = new ListItem(i + 1, dual ? i % 2 : 0,
                (i + 1).ToString("D5") + "    PLAYER " + (i + 1).ToString("D5") + "                        " + (100000 - i));
            return items;
        }
        internal static ListItem[] CopyAndValidate(IReadOnlyList<ListItem> source)
        {
            if (source == null) throw new ArgumentNullException(nameof(source));
            var ids = new HashSet<long>();
            var copy = new ListItem[source.Count];
            for (int i = 0; i < source.Count; i++)
            {
                var item = source[i];
                if (item == null || !ids.Add(item.Id)) throw new ArgumentException("Items require unique IDs and non-null entries.");
                copy[i] = item;
            }
            return copy;
        }
    }
    public struct ListPosition
    {
        public bool HasItem;
        public long ItemId;
        public int Index;
        public float Offset;
    }
}
