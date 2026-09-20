import React, { useState, useEffect } from 'react';
import { Play, Settings, History, MonitorPlay, UploadCloud, Download, CheckCircle2, AlertCircle } from 'lucide-react';

const API_URL = 'http://localhost:8000/api';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('execute');
  const [plugins, setPlugins] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [selectedPlugin, setSelectedPlugin] = useState('');
  
  // States for Execution
  const [file, setFile] = useState(null);
  const [manualText, setManualText] = useState('');
  const [configValues, setConfigValues] = useState({});
  const [isExecuting, setIsExecuting] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchPlugins();
    fetchTasks();
    const interval = setInterval(fetchTasks, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchPlugins = async () => {
    try {
      const res = await fetch(`${API_URL}/plugins`);
      const data = await res.json();
      setPlugins(data);
      if (data.length > 0) {
        setSelectedPlugin(data[0].name);
        fetchPluginConfig(data[0].name);
      }
    } catch (err) {
      console.error('Erro ao buscar plugins:', err);
    }
  };

  const fetchPluginConfig = async (pluginName) => {
    try {
      const res = await fetch(`${API_URL}/config/${pluginName}`);
      const data = await res.json();
      setConfigValues(data || {});
    } catch (err) {
      console.error('Erro ao buscar config:', err);
    }
  };

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_URL}/tasks`);
      const data = await res.json();
      setTasks(data);
    } catch (err) {
      console.error('Erro ao buscar histórico:', err);
    }
  };

  const handlePluginChange = (e) => {
    const name = e.target.value;
    setSelectedPlugin(name);
    fetchPluginConfig(name);
  };

  const handleConfigChange = (key, value) => {
    setConfigValues(prev => ({ ...prev, [key]: value }));
  };

  const saveConfig = async () => {
    try {
      await fetch(`${API_URL}/config/${selectedPlugin}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configValues)
      });
      setMessage({ type: 'success', text: 'Configurações salvas com sucesso!' });
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setMessage({ type: 'error', text: 'Erro ao salvar configurações' });
    }
  };

  const handleExecute = async () => {
    if (!file && !manualText) {
      setMessage({ type: 'error', text: 'Forneça um arquivo ou lista de CPFs' });
      return;
    }

    setIsExecuting(true);
    await saveConfig(); // Auto-save configs before run

    const formData = new FormData();
    formData.append('plugin_name', selectedPlugin);
    
    if (file) {
      formData.append('file', file);
    } else {
      // Convert manual text to a temp file
      const blob = new Blob([manualText], { type: 'text/plain' });
      formData.append('file', blob, 'manual_input.txt');
    }

    try {
      const res = await fetch(`${API_URL}/execute`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      
      if (res.ok) {
        setMessage({ type: 'success', text: 'Automação iniciada! Mudando para a tela do robô...' });
        setFile(null);
        setManualText('');
        fetchTasks();
        setTimeout(() => {
          setMessage(null);
          setActiveTab('browser');
        }, 2000);
      } else {
        setMessage({ type: 'error', text: data.detail || 'Erro ao iniciar' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Erro de comunicação com o servidor' });
    } finally {
      setIsExecuting(false);
    }
  };

  const renderConfigForm = () => {
    const plugin = plugins.find(p => p.name === selectedPlugin);
    if (!plugin || !plugin.required_configs) return null;

    return (
      <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-slate-800 flex items-center gap-2">
            <Settings className="w-5 h-5 text-slate-500" />
            Configuração do Site
          </h3>
          <button onClick={saveConfig} className="text-sm bg-slate-200 hover:bg-slate-300 px-3 py-1 rounded text-slate-700 font-medium">
            Salvar Apenas
          </button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {plugin.required_configs.map(field => (
            <div key={field.key}>
              <label className="block text-sm font-medium text-slate-700 mb-1">{field.label}</label>
              <input
                type={field.type}
                className="w-full border border-slate-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={configValues[field.key] || ''}
                onChange={(e) => handleConfigChange(field.key, e.target.value)}
                placeholder={`Digite ${field.label.toLowerCase()}`}
              />
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-3">
          <MonitorPlay className="text-blue-600" />
          RPA Automator
        </h1>
        <div className="flex bg-slate-100 rounded-lg p-1">
          <button 
            onClick={() => setActiveTab('execute')}
            className={`px-4 py-2 rounded-md font-medium text-sm flex items-center gap-2 transition-colors ${activeTab === 'execute' ? 'bg-white shadow text-blue-600' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <Play className="w-4 h-4" /> Executar
          </button>
          <button 
            onClick={() => setActiveTab('browser')}
            className={`px-4 py-2 rounded-md font-medium text-sm flex items-center gap-2 transition-colors ${activeTab === 'browser' ? 'bg-white shadow text-blue-600' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <MonitorPlay className="w-4 h-4" /> Ver Robô
          </button>
          <button 
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2 rounded-md font-medium text-sm flex items-center gap-2 transition-colors ${activeTab === 'history' ? 'bg-white shadow text-blue-600' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <History className="w-4 h-4" /> Histórico
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6 max-w-6xl w-full mx-auto">
        
        {message && (
          <div className={`mb-6 p-4 rounded-md flex items-center gap-3 ${message.type === 'error' ? 'bg-red-50 text-red-800 border border-red-200' : 'bg-green-50 text-green-800 border border-green-200'}`}>
            {message.type === 'error' ? <AlertCircle className="w-5 h-5" /> : <CheckCircle2 className="w-5 h-5" />}
            {message.text}
          </div>
        )}

        {/* Tab: Execute */}
        {activeTab === 'execute' && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="mb-6">
              <label className="block text-sm font-semibold text-slate-700 mb-2">Selecione o Módulo RPA (Site)</label>
              <select 
                className="w-full md:w-1/2 border border-slate-300 rounded-md px-3 py-2 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={selectedPlugin}
                onChange={handlePluginChange}
              >
                {plugins.map(p => (
                  <option key={p.name} value={p.name}>{p.display_name}</option>
                ))}
              </select>
            </div>

            {renderConfigForm()}

            <div className="mb-8">
              <h3 className="text-lg font-medium text-slate-800 mb-4">Dados de Entrada</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="border-2 border-dashed border-slate-300 rounded-lg p-6 flex flex-col items-center justify-center text-center hover:bg-slate-50 transition-colors">
                  <UploadCloud className="w-10 h-10 text-slate-400 mb-3" />
                  <p className="text-sm text-slate-600 mb-2">Envie uma planilha (Excel/CSV) ou arquivo de Texto</p>
                  <input 
                    type="file" 
                    onChange={e => setFile(e.target.files[0])} 
                    className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                  />
                  {file && <p className="mt-2 text-sm text-green-600 font-medium">Arquivo selecionado: {file.name}</p>}
                </div>
                
                <div className="flex flex-col">
                  <p className="text-sm text-slate-600 mb-2 font-medium">Ou cole os CPFs manualmente (um por linha):</p>
                  <textarea 
                    className="flex-1 border border-slate-300 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Ex: 123.456.789-00&#10;98765432100"
                    value={manualText}
                    onChange={e => setManualText(e.target.value)}
                    disabled={!!file}
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button 
                onClick={handleExecute}
                disabled={isExecuting}
                className={`px-6 py-3 rounded-lg font-bold text-white flex items-center gap-2 ${isExecuting ? 'bg-slate-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 shadow-md'}`}
              >
                {isExecuting ? 'Iniciando...' : <><Play className="w-5 h-5" /> Iniciar Automação</>}
              </button>
            </div>
          </div>
        )}

        {/* Tab: Browser (NoVNC) */}
        {activeTab === 'browser' && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col" style={{ height: '75vh' }}>
            <div className="bg-slate-800 text-white px-4 py-2 flex items-center justify-between text-sm">
              <span className="flex items-center gap-2"><MonitorPlay className="w-4 h-4"/> Visualização ao Vivo do Robô</span>
              <span className="text-slate-400">Apenas leitura (Não interfira na automação)</span>
            </div>
            {/* O NoVNC por padrão vem no vnc.html, ou vnc_lite.html. 
                Porta 7900 é mapeada no docker-compose para o host */}
            <iframe 
              src="http://localhost:7900/vnc.html?autoconnect=true&resize=remote"
              className="w-full flex-1 bg-black border-none"
              title="Robo Browser"
            ></iframe>
          </div>
        )}

        {/* Tab: History */}
        {activeTab === 'history' && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h2 className="text-xl font-bold text-slate-800 mb-6">Histórico de Execuções</h2>
            
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b-2 border-slate-200 text-sm text-slate-500 uppercase tracking-wider">
                    <th className="p-3">ID</th>
                    <th className="p-3">Data</th>
                    <th className="p-3">Site/Plugin</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Progresso</th>
                    <th className="p-3 text-right">Ação</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map(task => (
                    <tr key={task.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="p-3 font-medium text-slate-900">#{task.id}</td>
                      <td className="p-3 text-slate-600">
                        {new Date(task.created_at).toLocaleString()}
                      </td>
                      <td className="p-3 text-slate-600">{task.plugin_name}</td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold
                          ${task.status === 'completed' ? 'bg-green-100 text-green-700' : 
                            task.status === 'error' ? 'bg-red-100 text-red-700' : 
                            task.status === 'running_rpa' ? 'bg-blue-100 text-blue-700 animate-pulse' : 
                            'bg-yellow-100 text-yellow-700'}`}>
                          {task.status.replace('_', ' ').toUpperCase()}
                        </span>
                      </td>
                      <td className="p-3 text-slate-600 text-sm">
                        {task.processed_cpfs} / {task.total_cpfs} CPFs
                      </td>
                      <td className="p-3 text-right">
                        {task.status === 'completed' && task.file_path_output ? (
                          <a 
                            href={`http://localhost:8000/outputs/${task.file_path_output.split('/').pop().split('\\\\').pop()}`}
                            download
                            className="inline-flex items-center gap-1 text-sm bg-green-50 text-green-700 px-3 py-1.5 rounded hover:bg-green-100 font-medium transition-colors"
                          >
                            <Download className="w-4 h-4" /> Baixar Planilha
                          </a>
                        ) : (
                          <span className="text-slate-400 text-sm">Indisponível</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {tasks.length === 0 && (
                    <tr>
                      <td colSpan="6" className="p-8 text-center text-slate-500">
                        Nenhuma tarefa encontrada.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
