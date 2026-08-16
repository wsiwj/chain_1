// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title EventLedger
/// @notice The "notebook": an append-only log of AI-agent-verified events,
///         plus an access/automation switchboard. Only authorized agents
///         may write; pages can never be edited or deleted.
contract EventLedger {
    // --- roles ---
    address public owner;                     // manages who counts as an agent
    mapping(address => bool) public isAgent;  // may log events & flip access

    // --- one "page" in the notebook ---
    struct EventRecord {
        bytes32 evidenceHash; // SHA-256 fingerprint of the raw image/audio (media stays off-chain)
        uint40  timestamp;    // when the page was written (block time)
        address reporter;     // which agent wrote it
        string  label;        // the AI's description, e.g. "person at door"
    }
    EventRecord[] private events;

    // --- the switchboard: who/what is currently allowed ---
    mapping(address => bool) public accessAllowed;

    // --- announcements (indexable from off-chain) ---
    event EventLogged(uint256 indexed id, bytes32 indexed evidenceHash, address indexed reporter, string label);
    event AccessChanged(address indexed subject, bool allowed, address indexed changedBy);
    event AgentSet(address indexed agent, bool enabled);

    // --- guards ---
    error NotOwner();
    error NotAgent();

    modifier onlyOwner() { if (msg.sender != owner) revert NotOwner(); _; }
    modifier onlyAgent() { if (!isAgent[msg.sender]) revert NotAgent(); _; }

    constructor() {
        owner = msg.sender;
        isAgent[msg.sender] = true; // deployer is the first agent
        emit AgentSet(msg.sender, true);
    }

    // --- agent management (owner only) ---
    function setAgent(address agent, bool enabled) external onlyOwner {
        isAgent[agent] = enabled;
        emit AgentSet(agent, enabled);
    }

    // --- job 1: write a page (log a verified event) ---
    function logEvent(bytes32 evidenceHash, string calldata label)
        external
        onlyAgent
        returns (uint256 id)
    {
        id = events.length;
        events.push(EventRecord({
            evidenceHash: evidenceHash,
            timestamp: uint40(block.timestamp),
            reporter: msg.sender,
            label: label
        }));
        emit EventLogged(id, evidenceHash, msg.sender, label);
    }

    // --- job 2: flip a switch (allow/deny access) ---
    function setAccess(address subject, bool allowed) external onlyAgent {
        accessAllowed[subject] = allowed;
        emit AccessChanged(subject, allowed, msg.sender);
    }

    /// @notice Atomic "decide + record": flip access AND log why, in one transaction.
    ///         Guarantees you never have a flipped switch without a written reason.
    function decideAccess(address subject, bool allowed, bytes32 evidenceHash, string calldata label)
        external
        onlyAgent
        returns (uint256 id)
    {
        accessAllowed[subject] = allowed;
        emit AccessChanged(subject, allowed, msg.sender);

        id = events.length;
        events.push(EventRecord(evidenceHash, uint40(block.timestamp), msg.sender, label));
        emit EventLogged(id, evidenceHash, msg.sender, label);
    }

    // --- reading the notebook (free, anyone can) ---
    function eventCount() external view returns (uint256) {
        return events.length;
    }

    function getEvent(uint256 id) external view returns (EventRecord memory) {
        return events[id];
    }

    function isAllowed(address subject) external view returns (bool) {
        return accessAllowed[subject];
    }
}
