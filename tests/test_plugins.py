import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import asyncio

from host.plugins.plugin_base import (
    Plugin, PluginInfo, PluginContext, PluginResult, PluginType,
    PluginStatus, CommandPlugin, FilterPlugin, ProviderPlugin, ExtensionPlugin
)
from host.plugins.plugin_manager import PluginManager, PluginInstance, PluginExecutionRequest, PluginExecutionResult
from host.plugins.plugin_loader import PluginLoader, PluginLoadResult, PluginDiscoveryResult


class DummyCommandPlugin(CommandPlugin):
    
    def __init__(self):
        self._initialized = False
        self._shutdown_called = False
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="dummy_command",
            name="Dummy Command",
            version="1.0.0",
            type=PluginType.COMMAND,
            author="Test",
            description="Test plugin"
        )
    
    async def initialize(self, context: PluginContext) -> PluginResult:
        self._initialized = True
        return PluginResult(success=True, message="Initialized")
    
    async def shutdown(self) -> PluginResult:
        self._shutdown_called = True
        return PluginResult(success=True, message="Shutdown")
    
    async def execute(self, params: dict) -> PluginResult:
        return PluginResult(success=True, message="Executed", data=params)


class DummyFilterPlugin(FilterPlugin):
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="dummy_filter",
            name="Dummy Filter",
            version="1.0.0",
            type=PluginType.FILTER,
            author="Test",
            description="Test filter plugin"
        )
    
    async def initialize(self, context: PluginContext) -> PluginResult:
        return PluginResult(success=True, message="Initialized")
    
    async def shutdown(self) -> PluginResult:
        return PluginResult(success=True, message="Shutdown")
    
    async def filter(self, data: any, context: dict = None) -> PluginResult:
        return PluginResult(success=True, message="Filtered", data={"filtered": data})


@pytest.mark.asyncio
async def test_plugin_info_creation():
    info = PluginInfo(
        id="test_plugin",
        name="Test Plugin",
        version="1.0.0",
        type=PluginType.COMMAND,
        author="Test Author",
        description="A test plugin"
    )
    
    assert info.id == "test_plugin"
    assert info.name == "Test Plugin"
    assert info.type == PluginType.COMMAND
    assert info.version == "1.0.0"


@pytest.mark.asyncio
async def test_plugin_context_creation():
    context = PluginContext(
        system=Mock(),
        agent=Mock(),
        voice_manager=Mock(),
        protocol_client=Mock(),
        config={"test": "value"}
    )
    
    assert context.config["test"] == "value"
    assert context.system is not None


@pytest.mark.asyncio
async def test_plugin_result_success():
    result = PluginResult(
        success=True,
        message="Operation successful",
        data={"key": "value"}
    )
    
    assert result.success is True
    assert result.message == "Operation successful"
    assert result.data == {"key": "value"}


@pytest.mark.asyncio
async def test_plugin_result_failure():
    result = PluginResult(
        success=False,
        message="Operation failed",
        error_code="ERR_001"
    )
    
    assert result.success is False
    assert result.error_code == "ERR_001"


@pytest.mark.asyncio
async def test_command_plugin_execute():
    plugin = DummyCommandPlugin()
    
    result = await plugin.execute({"param": "value"})
    
    assert result.success is True
    assert result.data == {"param": "value"}


@pytest.mark.asyncio
async def test_filter_plugin_filter():
    plugin = DummyFilterPlugin()
    
    result = await plugin.filter("test data", {"context": "value"})
    
    assert result.success is True
    assert result.data["filtered"] == "test data"


@pytest.mark.asyncio
async def test_plugin_lifecycle():
    context = PluginContext(
        system=Mock(),
        agent=Mock(),
        voice_manager=Mock(),
        protocol_client=Mock(),
        config={}
    )
    
    plugin = DummyCommandPlugin()
    
    init_result = await plugin.initialize(context)
    assert init_result.success is True
    assert plugin._initialized is True
    
    shutdown_result = await plugin.shutdown()
    assert shutdown_result.success is True
    assert plugin._shutdown_called is True


@pytest.mark.asyncio
async def test_plugin_instance_creation():
    plugin = DummyCommandPlugin()
    
    instance = PluginInstance(plugin=plugin)
    
    assert instance.plugin == plugin
    assert instance.status == PluginStatus.LOADED
    assert instance.enabled is True


@pytest.mark.asyncio
async def test_plugin_manager_initialization():
    with tempfile.TemporaryDirectory() as tmpdir:
        context = PluginContext(
            system=Mock(),
            agent=Mock(),
            voice_manager=Mock(),
            protocol_client=Mock(),
            config={}
        )
        
        manager = PluginManager(
            plugin_dirs=[Path(tmpdir)],
            context=context,
            auto_load=False
        )
        
        assert manager.context == context
        assert len(manager.plugin_dirs) == 1
        assert manager._plugins == {}


@pytest.mark.asyncio
async def test_plugin_manager_load_plugin():
    with tempfile.TemporaryDirectory() as tmpdir:
        context = PluginContext(
            system=Mock(),
            agent=Mock(),
            voice_manager=Mock(),
            protocol_client=Mock(),
            config={}
        )
        
        manager = PluginManager(
            plugin_dirs=[Path(tmpdir)],
            context=context,
            auto_load=False
        )
        
        plugin = DummyCommandPlugin()
        
        with patch.object(manager.loader, 'load_plugin') as mock_load:
            mock_load.return_value = PluginLoadResult(
                plugin_id="dummy_command",
                plugin=plugin,
                success=True
            )
            
            instance = await manager.load_plugin(Path(tmpdir) / "test.py")
            
            assert instance is not None
            assert instance.status == PluginStatus.READY


@pytest.mark.asyncio
async def test_plugin_manager_unload_plugin():
    with tempfile.TemporaryDirectory() as tmpdir:
        context = PluginContext(
            system=Mock(),
            agent=Mock(),
            voice_manager=Mock(),
            protocol_client=Mock(),
            config={}
        )
        
        manager = PluginManager(
            plugin_dirs=[Path(tmpdir)],
            context=context,
            auto_load=False
        )
        
        plugin = DummyCommandPlugin()
        instance = PluginInstance(plugin=plugin, status=PluginStatus.READY)
        manager._plugins["dummy_command"] = instance
        
        result = await manager.unload_plugin("dummy_command")
        
        assert result is True
        assert "dummy_command" not in manager._plugins


@pytest.mark.asyncio
async def test_plugin_manager_execute_plugin():
    with tempfile.TemporaryDirectory() as tmpdir:
        context = PluginContext(
            system=Mock(),
            agent=Mock(),
            voice_manager=Mock(),
            protocol_client=Mock(),
            config={}
        )
        
        manager = PluginManager(
            plugin_dirs=[Path(tmpdir)],
            context=context,
            auto_load=False
        )
        
        plugin = DummyCommandPlugin()
        instance = PluginInstance(plugin=plugin, status=PluginStatus.READY)
        manager._plugins["dummy_command"] = instance
        
        request = PluginExecutionRequest(
            plugin_id="dummy_command",
            method="execute",
            kwargs={"param": "test"}
        )
        
        result = await manager.execute_plugin(request)
        
        assert result.success is True
        assert result.result is not None


@pytest.mark.asyncio
async def test_plugin_manager_broadcast_event():
    with tempfile.TemporaryDirectory() as tmpdir:
        context = PluginContext(
            system=Mock(),
            agent=Mock(),
            voice_manager=Mock(),
            protocol_client=Mock(),
            config={}
        )
        
        manager = PluginManager(
            plugin_dirs=[Path(tmpdir)],
            context=context,
            auto_load=False
        )
        
        plugin = DummyCommandPlugin()
        instance = PluginInstance(plugin=plugin, status=PluginStatus.READY)
        manager._plugins["dummy_command"] = instance
        
        results = await manager.broadcast_event("test_event", {"data": "value"})
        
        assert len(results) == 1


@pytest.mark.asyncio
async def test_plugin_manager_get_plugin_by_type():
    with tempfile.TemporaryDirectory() as tmpdir:
        context = PluginContext(
            system=Mock(),
            agent=Mock(),
            voice_manager=Mock(),
            protocol_client=Mock(),
            config={}
        )
        
        manager = PluginManager(
            plugin_dirs=[Path(tmpdir)],
            context=context,
            auto_load=False
        )
        
        plugin = DummyCommandPlugin()
        instance = PluginInstance(plugin=plugin, status=PluginStatus.READY)
        manager._plugins["dummy_command"] = instance
        manager._plugin_map[PluginType.COMMAND]["dummy_command"] = instance
        
        command_plugins = manager.get_plugins_by_type(PluginType.COMMAND)
        
        assert len(command_plugins) == 1
        assert command_plugins[0].plugin == plugin


@pytest.mark.asyncio
async def test_plugin_manager_enable_disable():
    with tempfile.TemporaryDirectory() as tmpdir:
        context = PluginContext(
            system=Mock(),
            agent=Mock(),
            voice_manager=Mock(),
            protocol_client=Mock(),
            config={}
        )
        
        manager = PluginManager(
            plugin_dirs=[Path(tmpdir)],
            context=context,
            auto_load=False
        )
        
        plugin = DummyCommandPlugin()
        instance = PluginInstance(plugin=plugin, status=PluginStatus.READY)
        manager._plugins["dummy_command"] = instance
        
        await manager.disable_plugin("dummy_command")
        assert instance.enabled is False
        
        await manager.enable_plugin("dummy_command")
        assert instance.enabled is True


@pytest.mark.asyncio
async def test_plugin_loader_initialization():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader([Path(tmpdir)])
        
        assert len(loader.plugin_dirs) == 1
        assert loader.recursive is True


@pytest.mark.asyncio
async def test_plugin_loader_discovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader([Path(tmpdir)])
        
        test_file = Path(tmpdir) / "test_plugin.py"
        test_file.write_text("""
from host.plugins.plugin_base import Plugin, PluginInfo, PluginType, CommandPlugin, PluginContext, PluginResult

class TestPlugin(CommandPlugin):
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            type=PluginType.COMMAND,
            author="Test",
            description="Test"
        )
    
    async def initialize(self, context: PluginContext) -> PluginResult:
        return PluginResult(success=True)
    
    async def shutdown(self) -> PluginResult:
        return PluginResult(success=True)
    
    async def execute(self, params: dict) -> PluginResult:
        return PluginResult(success=True)
""")
        
        results = await loader.discover_plugins()
        
        assert "test_plugin_test_plugin" in results


@pytest.mark.asyncio
async def test_plugin_loader_load_plugin():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader([Path(tmpdir)])
        
        plugin = DummyCommandPlugin()
        
        with patch.object(loader, '_discover_file') as mock_discover:
            mock_discover.return_value = PluginDiscoveryResult(
                plugin_path=Path(tmpdir) / "test.py",
                plugin_id="dummy_command",
                plugin_class=type(plugin),
                info=plugin.info,
                loadable=True
            )
            
            result = await loader.load_plugin(Path(tmpdir) / "test.py")
            
            assert result.success is True
            assert result.plugin_id == "dummy_command"


@pytest.mark.asyncio
async def test_plugin_execution_request():
    request = PluginExecutionRequest(
        plugin_id="test_plugin",
        method="execute",
        kwargs={"param": "value"},
        timeout=10.0
    )
    
    assert request.plugin_id == "test_plugin"
    assert request.method == "execute"
    assert request.kwargs == {"param": "value"}
    assert request.timeout == 10.0


@pytest.mark.asyncio
async def test_plugin_execution_result():
    result = PluginExecutionResult(
        plugin_id="test_plugin",
        success=True,
        result={"data": "value"},
        execution_time=0.5
    )
    
    assert result.plugin_id == "test_plugin"
    assert result.success is True
    assert result.result == {"data": "value"}
    assert result.execution_time == 0.5


@pytest.mark.asyncio
async def test_plugin_manager_export_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        context = PluginContext(
            system=Mock(),
            agent=Mock(),
            voice_manager=Mock(),
            protocol_client=Mock(),
            config={}
        )
        
        manager = PluginManager(
            plugin_dirs=[Path(tmpdir)],
            context=context,
            auto_load=False
        )
        
        plugin = DummyCommandPlugin()
        instance = PluginInstance(plugin=plugin, status=PluginStatus.READY)
        manager._plugins["dummy_command"] = instance
        
        config = manager.export_config("dummy_command")
        
        assert config is not None


@pytest.mark.asyncio
async def test_plugin_manager_save_load_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        context = PluginContext(
            system=Mock(),
            agent=Mock(),
            voice_manager=Mock(),
            protocol_client=Mock(),
            config={}
        )
        
        manager = PluginManager(
            plugin_dirs=[Path(tmpdir)],
            context=context,
            auto_load=False
        )
        
        plugin = DummyCommandPlugin()
        instance = PluginInstance(plugin=plugin, status=PluginStatus.READY, enabled=True)
        manager._plugins["dummy_command"] = instance
        
        state_file = Path(tmpdir) / "plugin_state.json"
        
        result = manager.save_state(state_file)
        assert result is True
        
        assert state_file.exists()
