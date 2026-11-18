import { Link } from 'react-router-dom';
import { Check, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { LogoMark } from '@/components/ui/Logo';

const plans = [
  { name: 'Free', price: 'R$ 0', period: '/para sempre', features: ['Até 5 clientes cadastrados', 'Registro das etapas do relacionamento', 'Acompanhamento manual de clientes e pagamentos', 'Visão geral da carteira'], cta: 'Começar grátis' },
  { name: 'Pro', price: 'R$ 24,90', period: '/mês', features: ['Clientes ilimitados', 'Dashboard completo com indicadores comerciais', 'Conexão com WhatsApp pelo QR Code', 'Mensagens de follow-up personalizadas', 'Envio automático de cobranças e follow-ups', 'Histórico de mensagens enviadas', 'Suporte prioritário'], cta: 'Assinar o Pro', popular: true },
];
const faqs = [
  { q: 'Posso mudar de plano quando quiser?', a: 'Sim. Você pode fazer upgrade quando precisar de mais recursos.' },
  { q: 'Como funciona a conexão com WhatsApp?', a: 'Você conecta seu próprio número lendo um QR Code, de forma semelhante ao WhatsApp Web. A conexão pode ser encerrada pelo WhatsApp e precisará ser refeita quando isso acontecer.' },
  { q: 'As mensagens de follow-up são personalizáveis?', a: 'Sim. Você pode editar os modelos de mensagem e escolher quais situações terão envio automático ou ficarão disponíveis para envio manual.' },
  { q: 'Posso cancelar minha assinatura?', a: 'Sim. Você pode cancelar a qualquer momento. O acesso permanece até o fim do período já pago.' },
];

export default function PricingPage() {
  return <div className="min-h-screen bg-surface-950 text-white">
    <nav className="sticky top-0 z-50 border-b border-white/5 bg-surface-950/80 backdrop-blur-xl"><div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8"><Link to="/" className="flex items-center gap-3"><LogoMark className="h-9 w-9 rounded-[25%]" /><span className="text-xl font-bold bg-gradient-to-r from-brand-400 to-accent-400 bg-clip-text text-transparent">TexasCRM</span></Link><div className="flex items-center gap-3"><Link to="/login"><Button variant="ghost" size="sm" className="!text-surface-300">Entrar</Button></Link><Link to="/register"><Button size="sm">Começar grátis</Button></Link></div></div></nav>
    <main className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
      <header className="mb-14 text-center"><h1 className="mb-4 text-4xl font-bold sm:text-5xl">Um plano simples para organizar seus clientes</h1><p className="mx-auto max-w-2xl text-lg text-surface-400">Comece gratuitamente e tenha mais recursos para acompanhar seus clientes e automatizar seus retornos quando precisar.</p></header>
      <div className="mx-auto mb-24 grid max-w-4xl gap-8 md:grid-cols-2">{plans.map(plan => <section key={plan.name} className={`relative rounded-2xl p-8 ${plan.popular ? 'border-2 border-brand-500/40 bg-gradient-to-b from-brand-500/10 to-brand-900/20 shadow-xl shadow-brand-500/10' : 'border border-white/[0.08] bg-white/[0.03]'}`}>{plan.popular && <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-600 px-4 py-1 text-xs font-semibold">Mais completo</span>}<h2 className="mb-2 text-xl font-bold">{plan.name}</h2><div className="mb-6 flex items-baseline gap-1"><span className="text-4xl font-extrabold">{plan.price}</span><span className="text-surface-400">{plan.period}</span></div><ul className="mb-8 space-y-3">{plan.features.map(f => <li key={f} className="flex items-start gap-3 text-sm text-surface-300"><Check className="mt-0.5 h-4 w-4 shrink-0 text-accent-500" />{f}</li>)}</ul><Link to="/register"><Button variant={plan.popular ? 'primary' : 'outline'} className={`w-full ${!plan.popular ? '!border-white/20 !text-white' : ''}`}>{plan.cta}</Button></Link></section>)}</div>
      <section className="mx-auto max-w-3xl"><h2 className="mb-8 text-center text-3xl font-bold">Dúvidas frequentes</h2><div className="space-y-3">{faqs.map(f => <details key={f.q} className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-5"><summary className="cursor-pointer font-medium">{f.q}</summary><p className="mt-3 text-sm leading-relaxed text-surface-400">{f.a}</p></details>)}</div></section>
      <section className="relative mt-24 overflow-hidden rounded-3xl bg-gradient-to-r from-brand-600 to-brand-800 p-10 text-center sm:p-14"><h2 className="relative z-10 mb-4 text-3xl font-bold">Seus clientes merecem acompanhamento</h2><p className="relative z-10 mx-auto mb-8 max-w-xl text-brand-100">Organize os relacionamentos, encontre oportunidades e saiba quem precisa de atenção.</p><Link to="/register" className="relative z-10 inline-block"><Button size="lg" variant="secondary" rightIcon={<ArrowRight className="h-5 w-5" />}>Começar grátis</Button></Link></section>
    </main>
  </div>;
}
