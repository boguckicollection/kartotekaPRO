import React from 'react';

interface OrderItem {
  name?: string;
  code?: string;
  quantity?: number;
  price?: number;
}

interface Order {
  id?: number | string;
  date?: string;
  total?: number | string;
  items?: OrderItem[];
  buyer?: {
    firstname?: string;
    lastname?: string;
    email?: string;
    phone?: string;
    city?: string;
    postcode?: string;
    street1?: string;
  };
  delivery_fullname?: string;
}

interface ThermalReceiptProps {
  order: Order | null;
}

export const ThermalReceipt = React.forwardRef<HTMLDivElement, ThermalReceiptProps>((props, ref) => {
  const { order } = props;

  if (!order) {
    return <div ref={ref} />;
  }

  const items = order.items || [];
  const itemsTotal = items.reduce((acc, p) => acc + (Number(p.price || 0) * Number(p.quantity || 1)), 0);
  const orderTotal = order.total != null 
    ? Number(String(order.total).replace(',', '.')) 
    : itemsTotal;
  const shippingCost = Math.max(0, orderTotal - itemsTotal);

  // Get buyer name
  const buyerName = order.delivery_fullname 
    || (order.buyer ? `${order.buyer.firstname || ''} ${order.buyer.lastname || ''}`.trim() : '')
    || 'Klient';

  // Format date
  const orderDate = order.date 
    ? new Date(order.date).toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric' })
    : '';

  return (
    <div 
      ref={ref} 
      style={{ 
        width: '60mm', 
        minHeight: '80mm',
        padding: '4mm', 
        boxSizing: 'border-box', 
        backgroundColor: 'white', 
        color: 'black', 
        fontFamily: 'Consolas, Monaco, "Courier New", monospace',
        fontSize: '9pt',
        lineHeight: '1.3',
      }}
    >
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '3mm' }}>
        <div style={{ 
          fontSize: '14pt', 
          fontWeight: 'bold', 
          letterSpacing: '1px',
          marginBottom: '1mm'
        }}>
          KARTOTEKA.SHOP
        </div>
        <div style={{ fontSize: '8pt', color: '#333' }}>
          Dziękujemy za zakup!
        </div>
      </div>

      {/* Separator */}
      <div style={{ 
        borderTop: '1px dashed #000', 
        margin: '2mm 0' 
      }} />

      {/* Order info */}
      <div style={{ marginBottom: '2mm' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '8pt' }}>
          <span>Zamówienie #{order.id}</span>
          <span>{orderDate}</span>
        </div>
        <div style={{ marginTop: '1mm', fontWeight: 'bold' }}>
          {buyerName}
        </div>
      </div>

      {/* Separator */}
      <div style={{ 
        borderTop: '1px dashed #000', 
        margin: '2mm 0' 
      }} />

      {/* Items list */}
      <div style={{ marginBottom: '2mm' }}>
        {items.length === 0 ? (
          <div style={{ fontSize: '8pt', color: '#666' }}>Brak pozycji</div>
        ) : (
          <ol style={{ 
            margin: 0, 
            paddingLeft: '4mm',
            listStyleType: 'decimal'
          }}>
            {items.map((item, index) => (
              <li key={index} style={{ marginBottom: '2mm', pageBreakInside: 'avoid' }}>
                <div style={{ 
                  fontSize: '8pt',
                  wordBreak: 'break-word'
                }}>
                  {item.name || 'Produkt'}
                </div>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between',
                  fontSize: '8pt',
                  color: '#333'
                }}>
                  <span>{item.quantity || 1} szt. × {Number(item.price || 0).toFixed(2)} zł</span>
                  <span style={{ fontWeight: 'bold' }}>
                    {(Number(item.price || 0) * Number(item.quantity || 1)).toFixed(2)} zł
                  </span>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>

      {/* Separator */}
      <div style={{ 
        borderTop: '1px dashed #000', 
        margin: '2mm 0' 
      }} />

      {/* Totals */}
      <div style={{ fontSize: '8pt' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1mm' }}>
          <span>Produkty:</span>
          <span>{itemsTotal.toFixed(2)} zł</span>
        </div>
        {shippingCost > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1mm' }}>
            <span>Wysyłka:</span>
            <span>{shippingCost.toFixed(2)} zł</span>
          </div>
        )}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between',
          fontSize: '11pt',
          fontWeight: 'bold',
          marginTop: '2mm',
          paddingTop: '1mm',
          borderTop: '1px solid #000'
        }}>
          <span>SUMA:</span>
          <span>{orderTotal.toFixed(2)} zł</span>
        </div>
      </div>

      {/* Footer */}
      <div style={{ 
        textAlign: 'center', 
        marginTop: '4mm',
        paddingTop: '2mm',
        borderTop: '1px dashed #000',
        fontSize: '7pt',
        color: '#666'
      }}>
        <div>Zapraszamy ponownie!</div>
        <div style={{ marginTop: '1mm' }}>kartoteka.shop</div>
      </div>
    </div>
  );
});

ThermalReceipt.displayName = 'ThermalReceipt';
