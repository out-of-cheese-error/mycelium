// Mycelium Desktop - Tauri Main Entry
// Spawns Python backend as sidecar and manages lifecycle

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use std::time::Duration;
use std::sync::Mutex;

#[tauri::command]
async fn get_backend_url() -> String {
    "http://localhost:8000".to_string()
}

// Wrapper for the backend process with Mutex for thread-safe access
struct BackendProcess(Mutex<Option<tauri_plugin_shell::process::CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let app_handle = app.handle().clone();
            
            // Spawn the Python backend sidecar
            tauri::async_runtime::spawn(async move {
                println!("Starting Mycelium backend...");
                
                let shell = app_handle.shell();
                
                // Spawn the sidecar process
                let sidecar_command = shell.sidecar("mycelium-backend")
                    .expect("Failed to create sidecar command");
                
                let (mut rx, child) = sidecar_command
                    .spawn()
                    .expect("Failed to spawn backend sidecar");
                
                // Store the child process handle for cleanup (wrapped in Mutex)
                app_handle.manage(BackendProcess(Mutex::new(Some(child))));
                
                // Log backend output
                tauri::async_runtime::spawn(async move {
                    use tauri_plugin_shell::process::CommandEvent;
                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line) => {
                                println!("[Backend] {}", String::from_utf8_lossy(&line));
                            }
                            CommandEvent::Stderr(line) => {
                                eprintln!("[Backend Error] {}", String::from_utf8_lossy(&line));
                            }
                            CommandEvent::Error(err) => {
                                eprintln!("[Backend Fatal] {}", err);
                            }
                            CommandEvent::Terminated(status) => {
                                println!("[Backend] Process terminated with status: {:?}", status);
                                break;
                            }
                            _ => {}
                        }
                    }
                });
                
                // Wait for backend to be ready
                wait_for_backend().await;
                println!("Backend is ready!");
            });
            
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                println!("Window closing, shutting down backend...");
                
                // Kill the backend process
                if let Some(backend) = window.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = backend.0.lock() {
                        if let Some(child) = guard.take() {
                            match child.kill() {
                                Ok(_) => println!("Backend process killed successfully"),
                                Err(e) => eprintln!("Failed to kill backend: {}", e),
                            }
                        }
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![get_backend_url])
        .run(tauri::generate_context!())
        .expect("error while running Mycelium");
}

async fn wait_for_backend() {
    let client = reqwest::Client::new();
    let health_url = "http://localhost:8000/health";
    
    for i in 0..30 {
        match client.get(health_url).send().await {
            Ok(response) if response.status().is_success() => {
                return;
            }
            _ => {
                if i % 5 == 0 {
                    println!("Waiting for backend... (attempt {})", i + 1);
                }
                tokio::time::sleep(Duration::from_millis(500)).await;
            }
        }
    }
    eprintln!("Warning: Backend health check timed out after 15 seconds");
}
