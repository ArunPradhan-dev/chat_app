
document.addEventListener("DOMContentLoaded", () => {
    const socket = io();
    const username = document.getElementById("username").textContent;
    window.username = username;
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.style.display = "none";
    document.body.appendChild(fileInput);
    document.getElementById("uploadBtn").addEventListener("click", () => {
    fileInput.click();
});
    let currentRoom = "general";
    let privateChatUser = null;
    let lastDisplayedDate = null;
    let lastMessageUser = null;
    const messagesDiv = document.getElementById("messages");
    const messageInput = document.getElementById("message");

    const emojiToggle = document.getElementById("emojiToggle");
    const emojiPanel = document.getElementById("emoji-panel");

    emojiToggle.addEventListener("click", () => {
        emojiPanel.classList.toggle("show");
    });
    document.addEventListener("click", function (event) {
    const isEmojiToggle = emojiToggle.contains(event.target);
    const isEmojiPanel = emojiPanel.contains(event.target);

    if (!isEmojiToggle && !isEmojiPanel) {
        emojiPanel.classList.remove("show");
    }
});


    emojiPanel.addEventListener("click", (e) => {
        if (e.target.tagName === "SPAN") {
        messageInput.value += e.target.textContent;
    //emojiPanel.classList.remove("show"); // close after selecting
        }
    });


     const currentRoomTitle = document.getElementById("current-room");
    
    
    //  typing indicators
let typingTimeout;
messageInput.addEventListener("input", () => {
    socket.emit("typing", { username, room: currentRoom, isTyping: true });

    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        socket.emit("typing", { username, room: currentRoom, isTyping: false });
    }, 2000);
});

    // Join default room
    socket.emit("join", { username, room: currentRoom });

    socket.emit("load_history", { room: currentRoom });

    // Receive messages
    socket.on("message", data => {
    console.log("Received:", data);
    addMessageToUI(data.message, data.timestamp, data.username);
});


    // Receive status messages 
    socket.on("status", data => {
        const status = document.createElement("div");
        status.className = "status";
        status.textContent = data.msg;
        messagesDiv.appendChild(status);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    });

    // Typing indicator
    socket.on("typing", data => {
        let typingEl = document.getElementById("typing");
        if (data.username !== username && data.isTyping) {
            if (!typingEl) {
                typingEl = document.createElement("div");
                typingEl.id = "typing";
                typingEl.className = "status";
                typingEl.textContent = `${data.username} is typing...`;
                messagesDiv.appendChild(typingEl);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        } else if (typingEl) {
            typingEl.remove();
        }
    });
    //online users
    socket.on("onlineUsers", users => {
    const list = document.getElementById("userList");
    list.innerHTML = "";

    users.forEach(user => {
        if (user === username) return;
        const li = document.createElement("li");
        li.classList.add("user-tooltip");
        li.textContent = user;

        const tooltip = document.createElement("span");
        tooltip.classList.add("tooltip-text");
        tooltip.textContent = "Start private chat";

        li.appendChild(tooltip);
        li.style.cursor = "pointer";

        // Click to invite to private chat
        li.addEventListener("click", () => {
            const privateRoom = getPrivateRoomName(username, user);
            socket.emit("private_chat_invite", {
                from: username,
                to: user,
                room: privateRoom
            });

            startPrivateChatWith(user); // Join immediately on sender side
        });

        list.appendChild(li);
    });
});


    // Send message on button click or enter key
    document.getElementById("sendBtn").addEventListener("click", sendMessage);
    messageInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendMessage();
        else socket.emit("typing", { username, room: currentRoom, isTyping: true });
    });
    messageInput.addEventListener("keyup", () => {
        setTimeout(() => {
            socket.emit("typing", { username, room: currentRoom, isTyping: false });
        }, 1000);
    });

    function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        if (privateChatUser) {
            const privateRoom = getPrivateRoomName(username, privateChatUser);
            socket.emit("message", { username, message, room: privateRoom });
        } else {
            socket.emit("message", { username, message, room: currentRoom });
        }
        messageInput.value = "";
    }

  function addMessageToUI(text, timestamp, username) {
    if (!username || !timestamp) return;

    const messageDate = new Date(timestamp);
    if (isNaN(messageDate)) return;

    //  date separator 
    const dateString = getDateLabel(messageDate);
    if (lastDisplayedDate !== dateString) {
        const dateSeparator = document.createElement("div");
        dateSeparator.className = "date-separator";
        dateSeparator.textContent = dateString;
        messagesDiv.appendChild(dateSeparator);
        lastDisplayedDate = dateString;
        lastMessageUser = null;
    }

    // Add username if it's a new sender 
    if (username !== lastMessageUser) {
        const displayName = username.charAt(0).toUpperCase() + username.slice(1);
        const nameDiv = document.createElement("div");
        nameDiv.className = "chat-username";
        nameDiv.classList.add(username === window.username ? "right" : "left");
        nameDiv.textContent = displayName;
        messagesDiv.appendChild(nameDiv);
        lastMessageUser = username;
    }

    //  Create message container 
    const msgDiv = document.createElement("div");
    msgDiv.className = "chat-message";

    // Align right for current user
    const alignmentClass = username === window.username ? "right" : "left";
    msgDiv.classList.add(alignmentClass);

    //  timestamp 
    const time = messageDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const timeSpan = document.createElement("span");
    timeSpan.className = "timestamp";
    timeSpan.textContent = `[${time}] `;

    const contentSpan = document.createElement("span");
    contentSpan.innerHTML = text;  

    msgDiv.appendChild(timeSpan);
    msgDiv.appendChild(contentSpan);
    messagesDiv.appendChild(msgDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}



function getDateLabel(date) {
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const isToday = date.toDateString() === today.toDateString();
    const isYesterday = date.toDateString() === yesterday.toDateString();

    if (isToday) return "Today";
    if (isYesterday) return "Yesterday";

    return date.toLocaleDateString(undefined, {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
    }); 
}



    //private chat
    function startPrivateChatWith(targetUser) {
    if (targetUser === username) return;

    if (privateChatUser) {
        const oldPrivateRoom = getPrivateRoomName(username, privateChatUser);
        socket.emit("leave", { username, room: oldPrivateRoom });
    } else {
        socket.emit("leave", { username, room: currentRoom });
    }

    privateChatUser = targetUser;
    const privateRoom = getPrivateRoomName(username, privateChatUser);
    currentRoom = privateRoom;

    socket.emit("join", { username, room: privateRoom });
    messagesDiv.innerHTML = "";
    socket.emit("load_history", { room: privateRoom });
    currentRoomTitle.textContent = `Private Chat with: ${privateChatUser}`;
}


    // Switch to a different room
    window.switchRoom = function(room) {
        if (room === currentRoom) return;
        if (privateChatUser) {
            const oldPrivateRoom = getPrivateRoomName(username, privateChatUser);
            socket.emit("leave", { username, room: oldPrivateRoom });
            privateChatUser = null;
        } else {
            socket.emit("leave", { username, room: currentRoom });
        }
        currentRoom = room;
        socket.emit("join", { username, room: currentRoom });
        messagesDiv.innerHTML = "";
        socket.emit("load_history", { room: currentRoom });
        currentRoomTitle.textContent = `Room: ${currentRoom}`;
    };

    
    function getPrivateRoomName(user1, user2) {
        return [user1, user2].sort().join('-');
    }

const themeToggle = document.getElementById("themeToggle");

// Load theme from localStorage
if (localStorage.getItem("theme") === "dark") {
    document.body.classList.add("dark-mode");
    themeToggle.textContent = "🌞 Light Mode";
}

// Toggle theme
themeToggle.addEventListener("click", () => {
    document.body.classList.toggle("dark-mode");

    if (document.body.classList.contains("dark-mode")) {
        localStorage.setItem("theme", "dark");
        themeToggle.textContent = "🌞 Light Mode";
    } else {
        localStorage.setItem("theme", "light");
        themeToggle.textContent = "🌙 Dark Mode";
    }
});

socket.on("chat_invite", data => {
    const inviteToast = document.getElementById("invite-toast");
    const inviteUser = document.getElementById("invite-user");
    inviteUser.textContent = data.from;
    inviteToast.style.display = "flex";

    // Join button
    document.getElementById("acceptInviteBtn").onclick = () => {
        inviteToast.style.display = "none";
        startPrivateChatWith(data.from);
    };

    // Ignore button
    document.getElementById("declineInviteBtn").onclick = () => {
        inviteToast.style.display = "none";
    };
});


//upload
fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    const progressContainer = document.getElementById("upload-progress-container");
    const progressBar = document.getElementById("upload-progress-bar");

    xhr.open("POST", "/upload", true);

    // Show progress container
    progressContainer.style.display = "block";
    progressBar.style.width = "0%";

    // Update progress bar as file uploads
    xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            progressBar.style.width = percent + "%";
        }
    });

    // When upload is done
    xhr.onload = () => {
        progressContainer.style.display = "none";

        if (xhr.status !== 200) {
            alert("Upload failed");
            return;
        }

        const data = JSON.parse(xhr.responseText);
        const ext = file.name.split('.').pop().toLowerCase();
        const fileUrl = data.url;

        const isImage = ['jpg', 'jpeg', 'png', 'gif'].includes(ext);
        const isVideo = ['mp4', 'webm', 'ogg'].includes(ext);

        let message;

        if (isImage) {
            message = `<img src="${fileUrl}" style="max-width: 200px; border-radius: 8px;" />`;
        } else if (isVideo) {
            message = `
                <video controls style="max-width: 250px; border-radius: 8px;">
                    <source src="${fileUrl}" type="video/${ext}">
                    Your browser does not support the video tag.
                </video>`;
        } else {
            message = `<a href="${fileUrl}" target="_blank" download>${file.name}</a>`;
        }

        socket.emit("message", {
            username,
            message,
            room: privateChatUser ? getPrivateRoomName(username, privateChatUser) : currentRoom
        });

        fileInput.value = ""; // reset
    };

    xhr.onerror = () => {
        progressContainer.style.display = "none";
        alert("Upload failed due to network error.");
    };

    xhr.send(formData);
});


//log out
document.getElementById("logoutBtn").addEventListener("click", () => {
    window.location.href = "/login";
});

const sidebarToggle = document.getElementById("sidebarToggle");
const chatSidebar = document.getElementById("chatSidebar");

sidebarToggle.addEventListener("click", () => {
  chatSidebar.classList.toggle("show");
});



});


