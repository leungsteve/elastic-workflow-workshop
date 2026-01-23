"""
CLI utilities for the Review Fraud Workshop.

Provides common Click options, config file loading, and environment variable
handling for admin CLI tools.
"""

import os
import functools
from pathlib import Path
from typing import Optional, Callable, Any, TypeVar

import click
from dotenv import load_dotenv

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import json
    JSON_AVAILABLE = True
except ImportError:
    JSON_AVAILABLE = False


F = TypeVar('F', bound=Callable[..., Any])


def load_env_file(env_path: Optional[str] = None) -> bool:
    """
    Load environment variables from a .env file.

    Searches for .env files in the following order:
    1. Explicitly provided path
    2. Current directory
    3. Parent directories up to the workspace root

    Args:
        env_path: Optional explicit path to .env file

    Returns:
        bool: True if a .env file was loaded, False otherwise
    """
    if env_path:
        if Path(env_path).exists():
            load_dotenv(env_path)
            return True
        else:
            click.echo(f"Warning: .env file not found at {env_path}", err=True)
            return False

    # Search for .env file
    current = Path.cwd()
    while current != current.parent:
        env_file = current / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            return True
        current = current.parent

    # Try default dotenv loading
    return load_dotenv()


def load_config_file(config_path: str) -> dict:
    """
    Load configuration from a YAML or JSON file.

    Args:
        config_path: Path to the configuration file

    Returns:
        dict: Configuration dictionary

    Raises:
        click.ClickException: If file not found or parsing fails
    """
    path = Path(config_path)

    if not path.exists():
        raise click.ClickException(f"Config file not found: {config_path}")

    suffix = path.suffix.lower()

    try:
        with open(path, 'r') as f:
            if suffix in ('.yaml', '.yml'):
                if not YAML_AVAILABLE:
                    raise click.ClickException(
                        "PyYAML is required for YAML config files. "
                        "Install with: pip install pyyaml"
                    )
                return yaml.safe_load(f) or {}

            elif suffix == '.json':
                return json.load(f)

            else:
                # Try to auto-detect format
                content = f.read()
                f.seek(0)

                # Try JSON first
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass

                # Try YAML
                if YAML_AVAILABLE:
                    try:
                        return yaml.safe_load(content) or {}
                    except yaml.YAMLError:
                        pass

                raise click.ClickException(
                    f"Unable to parse config file: {config_path}. "
                    "Supported formats: .yaml, .yml, .json"
                )

    except (yaml.YAMLError if YAML_AVAILABLE else Exception) as e:
        raise click.ClickException(f"Error parsing YAML config: {e}")
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Error parsing JSON config: {e}")


def common_options(func: F) -> F:
    """
    Decorator that adds common CLI options to a Click command.

    Adds the following options:
    - --dry-run: Preview changes without executing
    - --verbose / -v: Enable verbose output
    - --config / -c: Path to configuration file

    Example:
        >>> @click.command()
        ... @common_options
        ... def my_command(dry_run, verbose, config):
        ...     if verbose:
        ...         click.echo("Verbose mode enabled")
        ...     if dry_run:
        ...         click.echo("Dry run - no changes will be made")
    """
    @click.option(
        '--dry-run',
        is_flag=True,
        default=False,
        help='Preview changes without executing them.'
    )
    @click.option(
        '--verbose', '-v',
        is_flag=True,
        default=False,
        help='Enable verbose output.'
    )
    @click.option(
        '--config', '-c',
        type=click.Path(exists=False),
        default=None,
        help='Path to configuration file (YAML or JSON).'
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper  # type: ignore


def elasticsearch_options(func: F) -> F:
    """
    Decorator that adds Elasticsearch-related CLI options.

    Adds the following options:
    - --es-url: Elasticsearch URL
    - --es-api-key: API key for authentication
    - --es-username: Username for basic auth
    - --es-password: Password for basic auth

    These options override environment variables when provided.

    Example:
        >>> @click.command()
        ... @elasticsearch_options
        ... def my_command(es_url, es_api_key, es_username, es_password):
        ...     # Options are automatically set in environment
        ...     from admin.utils.elasticsearch import get_es_client
        ...     es = get_es_client()
    """
    @click.option(
        '--es-url',
        envvar='ELASTICSEARCH_URL',
        default=None,
        help='Elasticsearch URL (default: from ELASTICSEARCH_URL env var).'
    )
    @click.option(
        '--es-api-key',
        envvar='ELASTICSEARCH_API_KEY',
        default=None,
        help='Elasticsearch API key (default: from ELASTICSEARCH_API_KEY env var).'
    )
    @click.option(
        '--es-username',
        envvar='ELASTICSEARCH_USERNAME',
        default=None,
        help='Elasticsearch username (default: from ELASTICSEARCH_USERNAME env var).'
    )
    @click.option(
        '--es-password',
        envvar='ELASTICSEARCH_PASSWORD',
        default=None,
        help='Elasticsearch password (default: from ELASTICSEARCH_PASSWORD env var).'
    )
    @functools.wraps(func)
    def wrapper(*args, es_url, es_api_key, es_username, es_password, **kwargs):
        # Set environment variables if CLI options are provided
        if es_url:
            os.environ['ELASTICSEARCH_URL'] = es_url
        if es_api_key:
            os.environ['ELASTICSEARCH_API_KEY'] = es_api_key
        if es_username:
            os.environ['ELASTICSEARCH_USERNAME'] = es_username
        if es_password:
            os.environ['ELASTICSEARCH_PASSWORD'] = es_password

        return func(*args, **kwargs)

    return wrapper  # type: ignore


def env_option(func: F) -> F:
    """
    Decorator that adds a --env option for loading a specific .env file.

    Example:
        >>> @click.command()
        ... @env_option
        ... def my_command():
        ...     # .env file already loaded before command runs
        ...     pass
    """
    @click.option(
        '--env',
        type=click.Path(exists=True),
        default=None,
        help='Path to .env file to load.'
    )
    @functools.wraps(func)
    def wrapper(*args, env, **kwargs):
        load_env_file(env)
        return func(*args, **kwargs)

    return wrapper  # type: ignore


def confirm_action(
    message: str,
    default: bool = False,
    abort: bool = True
) -> bool:
    """
    Prompt user for confirmation before a destructive action.

    Args:
        message: Confirmation message to display
        default: Default value if user just presses Enter
        abort: If True, abort the command on 'no' response

    Returns:
        bool: True if confirmed, False otherwise

    Example:
        >>> if confirm_action("Delete all documents?"):
        ...     delete_documents()
    """
    return click.confirm(message, default=default, abort=abort)


def echo_success(message: str) -> None:
    """Print a success message in green."""
    click.echo(click.style(f"[OK] {message}", fg='green'))


def echo_warning(message: str) -> None:
    """Print a warning message in yellow."""
    click.echo(click.style(f"[WARNING] {message}", fg='yellow'), err=True)


def echo_error(message: str) -> None:
    """Print an error message in red."""
    click.echo(click.style(f"[ERROR] {message}", fg='red'), err=True)


def echo_info(message: str) -> None:
    """Print an info message in blue."""
    click.echo(click.style(f"[INFO] {message}", fg='blue'))


def echo_verbose(message: str, verbose: bool) -> None:
    """Print a message only if verbose mode is enabled."""
    if verbose:
        click.echo(click.style(f"[DEBUG] {message}", fg='cyan'))


class CliContext:
    """
    Context object for sharing state across CLI commands.

    Example:
        >>> @click.group()
        ... @click.pass_context
        ... def cli(ctx):
        ...     ctx.obj = CliContext()
        ...
        ... @cli.command()
        ... @click.pass_obj
        ... def subcommand(ctx: CliContext):
        ...     if ctx.verbose:
        ...         click.echo("Verbose!")
    """

    def __init__(
        self,
        verbose: bool = False,
        dry_run: bool = False,
        config: Optional[dict] = None
    ):
        """
        Initialize CLI context.

        Args:
            verbose: Whether verbose mode is enabled
            dry_run: Whether dry-run mode is enabled
            config: Configuration dictionary
        """
        self.verbose = verbose
        self.dry_run = dry_run
        self.config = config or {}

    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        echo_verbose(message, self.verbose)

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (supports dot notation: "section.key")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value


# Pre-load .env file when module is imported
load_env_file()
