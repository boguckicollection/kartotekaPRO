import React, { useState, useEffect } from 'react';

interface Attribute {
  attribute_id: string;
  name: string;
  options: { option_id: string; value: string }[];
}

interface Props {
  apiBase: string;
  scanId?: number | null;
  onSubmit: (attributes: Record<string, string>) => void;
  onCancel: () => void;
  onChangeSelections?: (data: { selected: Record<string,string>; finishLabel?: string; languageLabel?: string }) => void;
  forceFinishLabel?: string | null;
}

const AttributeForm: React.FC<Props> = ({ apiBase, scanId, onSubmit, onCancel, onChangeSelections, forceFinishLabel }) => {
  const [attributes, setAttributes] = useState<Attribute[]>([]);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchAttributes = async () => {
      try {
        setLoading(true)
        // 1) Fetch attributes from backend proxying Shoper API
        const res = await fetch(`${apiBase}/shoper/attributes`);
        const data = await res.json();
        const items: Attribute[] = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : []
        // Filter relevant groups by normalized name (case/diacritics-insensitive)
        const desiredRaw = ['Jakość','Jezyk','Język','Wykończenie','Wykonczenie','Rzadkość','Rzadkosc','Energia','Rodzaj','Typ','Typ Karty','Typ karty']
        const normalize = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase()
        const desired = new Set(desiredRaw.map(normalize))
        const relevantAttributes = items.filter((attr: any) => {
          const n = typeof attr?.name==='string' ? normalize(attr.name) : ''
          return desired.has(n)
        }) as Attribute[]
        setAttributes(relevantAttributes);

        // 2) Prefill defaults using server mapping for current scan if possible
        let defaults: Record<string, string> = {}
        if (scanId) {
          try {
            const r = await fetch(`${apiBase}/shoper/map_attributes?scan_id=${scanId}`, { method: 'POST' })
            const m = await r.json()
            const mapped = (m && m.attributes) || {}
            Object.entries(mapped).forEach(([attrId, optId]) => {
              defaults[String(attrId)] = String(optId)
            })
          } catch {}
        }
        // Fallback defaults (first option) only for missing ones
        relevantAttributes.forEach((attr: Attribute) => {
          if (!defaults[attr.attribute_id] && attr.options.length > 0) {
            defaults[attr.attribute_id] = attr.options[0].option_id
          }
        })
        setSelected(defaults)
      } catch (error) {
        console.error("Failed to fetch attributes:", error);
      }
      finally {
        setLoading(false)
      }
    };

    fetchAttributes();
  }, [apiBase, scanId]);

  // Apply external finish selection by label
  useEffect(() => {
    if (!forceFinishLabel) return;
    try {
      const norm = (s:string)=> s.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().trim()
      const finishKeys = new Set(['wykonczenie','wykończenie','finish'])
      const label = norm(forceFinishLabel)
      const finishAttr = attributes.find(a=> finishKeys.has(norm(a.name)))
      if (!finishAttr) return;
      const match = finishAttr.options.find(o=> norm(o.value).includes(label))
      if (!match) return;
      setSelected(prev => ({ ...prev, [finishAttr.attribute_id]: match.option_id }))
      if (onChangeSelections) {
        onChangeSelections({ selected: { ...(selected||{}), [finishAttr.attribute_id]: match.option_id }, finishLabel: match.value })
      }
    } catch {}
  }, [forceFinishLabel, attributes])

  const handleChange = (attribute_id: string, option_id: string) => {
    setSelected(prev => ({ ...prev, [attribute_id]: option_id }));
    try {
      if (onChangeSelections) {
        const attr = attributes.find(a=>a.attribute_id===attribute_id)
        const opt = attr?.options.find(o=>o.option_id===option_id)
        const name = (attr?.name||'').normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase()
        const finishKeys = new Set(['wykonczenie','wykończenie','finish'])
        const langKeys = new Set(['jezyk','język','language'])
        const payload: any = { selected: { ...(selected||{}), [attribute_id]: option_id } }
        if (attr && opt) {
          if (finishKeys.has(name)) payload.finishLabel = opt.value
          if (langKeys.has(name)) payload.languageLabel = opt.value
        }
        onChangeSelections(payload)
      }
    } catch {}
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(selected);
  };

  if (loading) {
    return <div>Ładowanie atrybutów…</div>;
  }
  if (attributes.length === 0) {
    return <div>Brak atrybutów do ustawienia.</div>;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4 border border-white/10 rounded-lg bg-[#0b1324] text-white">
      <h3 className="text-lg font-semibold">Atrybuty produktu</h3>
      {attributes.map(attr => (
        <div key={attr.attribute_id}>
          <label htmlFor={`attr-${attr.attribute_id}`} className="block text-sm font-medium text-gray-300">{attr.name}</label>
          <select
            id={`attr-${attr.attribute_id}`}
            value={selected[attr.attribute_id] || ''}
            onChange={e => handleChange(attr.attribute_id, e.target.value)}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base bg-[#101922] border border-gray-700 text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
          >
            <option value="">— wybierz —</option>
            {attr.options.map(opt => (
              <option key={opt.option_id} value={opt.option_id}>
                {opt.value}
              </option>
            ))}
          </select>
        </div>
      ))}
      <div className="flex justify-end space-x-2">
        <button type="button" onClick={onCancel} className="px-4 py-2 text-sm font-medium text-white bg-[#283039] border border-white/10 rounded-md hover:bg-[#2d3640]">
          Anuluj
        </button>
        <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-primary border border-transparent rounded-md hover:bg-primary/90">
          Zapisz
        </button>
      </div>
    </form>
  );
};

export default AttributeForm;
